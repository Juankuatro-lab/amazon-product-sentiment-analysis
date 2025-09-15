import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin, urlparse, parse_qs
import random
from datetime import datetime
import json
from textblob import TextBlob
import io

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Extracteur d'avis Amazon - Version Fonctionnelle",
    page_icon="📝",
    layout="wide"
)

class SentimentAnalyzer:
    """Analyseur de sentiment pour les commentaires"""
    
    @staticmethod
    def analyze_sentiment(text):
        """Analyse le sentiment d'un texte et retourne un label"""
        if not text or len(text.strip()) < 3:
            return "Neutre"
        
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            
            if polarity > 0.1:
                return "Positif"
            elif polarity < -0.1:
                return "Négatif"
            else:
                return "Neutre"
        except:
            return "Neutre"

class AmazonReviewsExtractor:
    def __init__(self):
        # Headers basés sur l'inspection réelle
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
    
    def clean_url(self, url):
        """Nettoie l'URL pour extraire l'URL de base du produit"""
        try:
            # Patterns pour extraire l'ASIN
            patterns = [
                r'/dp/([A-Z0-9]{10})',
                r'/product/([A-Z0-9]{10})',
                r'/gp/product/([A-Z0-9]{10})',
                r'asin=([A-Z0-9]{10})',
                r'/([A-Z0-9]{10})(?:/|$|[?&])'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    asin = match.group(1)
                    # Détecter le domaine Amazon
                    if "amazon.fr" in url:
                        domain = "amazon.fr"
                    elif "amazon.com" in url:
                        domain = "amazon.com"
                    elif "amazon.de" in url:
                        domain = "amazon.de"
                    elif "amazon.co.uk" in url:
                        domain = "amazon.co.uk"
                    else:
                        domain = "amazon.fr"  # Par défaut
                    
                    clean_product_url = f"https://www.{domain}/dp/{asin}"
                    return clean_product_url, asin, domain
            
            return None, None, None
        except Exception as e:
            st.error(f"Erreur lors du nettoyage de l'URL: {str(e)}")
            return None, None, None
    
    def extract_product_info_from_page(self, soup):
        """Extrait les informations de base du produit depuis la page"""
        try:
            # Note moyenne - sélecteurs basés sur la structure réelle
            avg_rating = None
            rating_selectors = [
                'span[data-hook="rating-out-of-text"]',
                'span.a-icon-alt',
                'i.a-icon-star span.a-offscreen',
                '.a-icon-star .a-offscreen'
            ]
            
            for selector in rating_selectors:
                try:
                    rating_elem = soup.select_one(selector)
                    if rating_elem:
                        rating_text = rating_elem.text or rating_elem.get('title', '')
                        rating_match = re.search(r'(\d+(?:[,\.]\d+)?)', rating_text)
                        if rating_match:
                            avg_rating = float(rating_match.group(1).replace(',', '.'))
                            break
                except:
                    continue
            
            # Nombre total d'avis
            total_reviews = 0
            review_count_selectors = [
                'span[data-hook="total-review-count"]',
                '#acrCustomerReviewText',
                'a[data-hook="see-all-reviews-link-foot"]'
            ]
            
            for selector in review_count_selectors:
                try:
                    reviews_elem = soup.select_one(selector)
                    if reviews_elem:
                        reviews_text = reviews_elem.text
                        numbers = re.findall(r'(\d+(?:[\s,\.]\d+)*)', reviews_text.replace(',', '').replace(' ', ''))
                        if numbers:
                            total_reviews = max([int(n) for n in numbers])
                            break
                except:
                    continue
            
            return {
                'avg_rating': avg_rating,
                'total_reviews': total_reviews
            }
            
        except Exception as e:
            return {'avg_rating': None, 'total_reviews': 0}
    
    def extract_single_review(self, review_element):
        """Extrait les informations d'un seul avis basé sur la structure HTML réelle"""
        try:
            review_data = {}
            
            # SÉLECTEUR EXACT basé sur le HTML fourni: i[data-hook="review-star-rating"] span.a-icon-alt
            rating = None
            rating_elem = review_element.select_one('i[data-hook="review-star-rating"] span.a-icon-alt')
            if rating_elem:
                rating_text = rating_elem.text
                # Recherche du pattern "X,X sur 5 étoiles"
                rating_match = re.search(r'(\d+(?:,\d+)?)', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1).replace(',', '.'))
            
            review_data['rating'] = rating
            
            # SÉLECTEUR EXACT basé sur le HTML fourni: 
            # span[data-hook="review-body"] > div > div[data-hook="review-collapsed"] > span
            content = ""
            
            # Méthode 1: Structure complète
            content_elem = review_element.select_one('span[data-hook="review-body"] div[data-hook="review-collapsed"] span')
            if content_elem:
                content = content_elem.get_text(strip=True)
            
            # Méthode 2: Fallback plus simple
            if not content:
                content_elem = review_element.select_one('span[data-hook="review-body"]')
                if content_elem:
                    # Extraire tout le texte en évitant les scripts et styles
                    for script in content_elem(["script", "style"]):
                        script.decompose()
                    content = content_elem.get_text(separator=' ', strip=True)
            
            # Nettoyer le contenu
            if content:
                # Supprimer les textes génériques Amazon
                content = re.sub(r'En savoir plus.*$', '', content)
                content = re.sub(r'Lire la suite.*$', '', content)
                content = re.sub(r'Read more.*$', '', content)
                content = re.sub(r'En lire plus.*$', '', content)
                content = content.strip()
            
            review_data['content'] = content
            
            # SÉLECTEUR pour le nom de l'auteur
            author = ""
            author_elem = review_element.select_one('span.a-profile-name')
            if author_elem:
                author = author_elem.get_text(strip=True)
            review_data['author'] = author
            
            # SÉLECTEUR pour la date
            date = ""
            date_elem = review_element.select_one('span[data-hook="review-date"]')
            if date_elem:
                date = date_elem.get_text(strip=True)
            review_data['date'] = date
            
            # SÉLECTEUR pour le titre
            title = ""
            title_elem = review_element.select_one('a[data-hook="review-title"] span')
            if title_elem:
                title = title_elem.get_text(strip=True)
            review_data['title'] = title
            
            # SÉLECTEUR pour achat vérifié
            verified = False
            verified_elem = review_element.select_one('span[data-hook="avp-badge-linkless"]')
            if verified_elem and "vérifié" in verified_elem.text.lower():
                verified = True
            review_data['verified_purchase'] = verified
            
            # SÉLECTEUR pour votes utiles
            helpful_votes = 0
            helpful_elem = review_element.select_one('span[data-hook="helpful-vote-statement"]')
            if helpful_elem:
                helpful_text = helpful_elem.text
                helpful_match = re.search(r'(\d+)', helpful_text)
                if helpful_match:
                    helpful_votes = int(helpful_match.group(1))
            review_data['helpful_votes'] = helpful_votes
            
            # Retourner seulement si on a du contenu valide
            return review_data if (rating is not None or (content and len(content) > 10)) else None
            
        except Exception as e:
            st.warning(f"Erreur extraction avis: {str(e)}")
            return None
    
    def extract_reviews_from_page(self, url, max_pages=2):
        """Extrait les avis depuis une page Amazon"""
        reviews = []
        session = requests.Session()
        session.headers.update(self.headers)
        
        for page in range(1, max_pages + 1):
            try:
                # Construire l'URL de la page
                if "pageNumber=" in url:
                    current_url = re.sub(r'pageNumber=\d+', f'pageNumber={page}', url)
                else:
                    separator = "&" if "?" in url else "?"
                    current_url = f"{url}{separator}pageNumber={page}"
                
                st.write(f"📖 Extraction page {page}: {current_url[:80]}...")
                
                # Pause aléatoire
                time.sleep(random.uniform(3, 6))
                
                response = session.get(current_url, timeout=15)
                
                if response.status_code != 200:
                    st.warning(f"⚠️ HTTP {response.status_code} pour la page {page}")
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # SÉLECTEUR EXACT basé sur le HTML fourni: li[data-hook="review"]
                review_elements = soup.select('li[data-hook="review"]')
                
                if not review_elements:
                    st.warning(f"⚠️ Aucun avis trouvé sur la page {page}")
                    break
                
                st.write(f"✅ Trouvé {len(review_elements)} avis sur la page {page}")
                
                page_reviews = 0
                for review_element in review_elements:
                    review_data = self.extract_single_review(review_element)
                    if review_data and review_data.get('content'):
                        reviews.append(review_data)
                        page_reviews += 1
                
                st.success(f"✅ Page {page}: {page_reviews} avis extraits avec contenu")
                
                if page_reviews == 0:
                    st.warning("⚠️ Aucun avis avec contenu, arrêt de l'extraction")
                    break
                
                # Vérifier s'il y a une page suivante
                next_disabled = soup.select_one('li.a-disabled.a-last')
                if next_disabled:
                    st.info("📄 Dernière page atteinte")
                    break
                    
            except Exception as e:
                st.error(f"❌ Erreur page {page}: {str(e)}")
                continue
        
        return reviews
    
    def extract_reviews_for_product(self, original_url, max_pages=2):
        """Méthode principale d'extraction"""
        try:
            # Nettoyer l'URL
            clean_url, asin, domain = self.clean_url(original_url)
            
            if not clean_url or not asin:
                st.error(f"❌ Impossible d'extraire l'ASIN depuis: {original_url}")
                return None
            
            st.info(f"🧹 URL nettoyée: {clean_url}")
            st.info(f"🆔 ASIN: {asin} | Domaine: {domain}")
            
            # Étape 1: Récupérer les infos de base depuis la page produit
            st.write("🔍 Extraction des informations produit...")
            session = requests.Session()
            session.headers.update(self.headers)
            
            time.sleep(random.uniform(2, 4))
            response = session.get(clean_url, timeout=15)
            
            product_info = None
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                product_info = self.extract_product_info_from_page(soup)
                st.success(f"✅ Info produit: {product_info.get('avg_rating', 'N/A')}/5 ⭐ | {product_info.get('total_reviews', 0)} avis")
            else:
                st.warning(f"⚠️ Impossible de récupérer la page produit (HTTP {response.status_code})")
            
            # Étape 2: Construire l'URL des avis
            # Basé sur la structure Amazon France
            reviews_base_url = f"https://www.{domain}/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews&sortBy=recent&pageNumber=1"
            
            st.info(f"📄 URL des avis: {reviews_base_url}")
            
            # Étape 3: Extraire les avis
            reviews = self.extract_reviews_from_page(reviews_base_url, max_pages)
            
            return {
                'product_info': product_info,
                'reviews': reviews,
                'asin': asin,
                'clean_url': clean_url
            }
            
        except Exception as e:
            st.error(f"❌ Erreur générale pour {original_url}: {str(e)}")
            return None

def process_batch_urls(urls, max_pages_per_product=2, progress_placeholder=None):
    """Traite une liste d'URLs en batch"""
    extractor = AmazonReviewsExtractor()
    analyzer = SentimentAnalyzer()
    results = []
    
    total_urls = len(urls)
    
    for i, url in enumerate(urls):
        if progress_placeholder:
            progress_placeholder.progress((i + 1) / total_urls)
            
        st.subheader(f"🔄 URL {i+1}/{total_urls}")
        st.write(f"**URL:** {url}")
        
        # Extraction des données pour ce produit
        product_data = extractor.extract_reviews_for_product(url.strip(), max_pages_per_product)
        
        if product_data and product_data['reviews']:
            product_info = product_data['product_info'] or {}
            reviews = product_data['reviews']
            
            # Calcul des statistiques
            total_reviews = product_info.get('total_reviews', len(reviews))
            avg_rating = product_info.get('avg_rating')
            if not avg_rating and reviews:
                ratings = [r['rating'] for r in reviews if r['rating'] is not None]
                avg_rating = sum(ratings) / len(ratings) if ratings else None
            
            # Création d'une ligne par avis
            for review in reviews:
                if review.get('content'):
                    sentiment = analyzer.analyze_sentiment(review['content'])
                    
                    results.append({
                        'url': url.strip(),
                        'nombre_avis': total_reviews,
                        'nombre_commentaires_client': len(reviews),
                        'moyenne_avis': round(avg_rating, 1) if avg_rating else None,
                        'avis_notation': review.get('rating'),
                        'commentaire_associe': review['content'],
                        'sentiment': sentiment,
                        'auteur': review.get('author', ''),
                        'date_avis': review.get('date', ''),
                        'titre_avis': review.get('title', ''),
                        'achat_verifie': review.get('verified_purchase', False),
                        'votes_utiles': review.get('helpful_votes', 0)
                    })
            
            st.success(f"✅ **Succès:** {len(reviews)} avis extraits!")
        else:
            st.error(f"❌ **Échec:** Aucun avis extrait")
            results.append({
                'url': url.strip(),
                'nombre_avis': 0,
                'nombre_commentaires_client': 0,
                'moyenne_avis': None,
                'avis_notation': None,
                'commentaire_associe': "Aucun avis extrait",
                'sentiment': "N/A",
                'auteur': '',
                'date_avis': '',
                'titre_avis': '',
                'achat_verifie': False,
                'votes_utiles': 0
            })
        
        st.markdown("---")
    
    return results

def main():
    st.title("📝 Extracteur d'avis Amazon - Version Basée sur HTML Réel")
    st.markdown("---")
    
    # Informations sur la version
    with st.expander("🎯 Version basée sur l'inspection HTML réelle", expanded=False):
        st.success("""
        **Cette version utilise les sélecteurs CSS exacts d'Amazon :**
        - ✅ `li[data-hook="review"]` pour chaque avis
        - ✅ `i[data-hook="review-star-rating"] span.a-icon-alt` pour les notes
        - ✅ `span[data-hook="review-body"]` pour le contenu
        - ✅ `span.a-profile-name` pour les auteurs
        - ✅ `span[data-hook="review-date"]` pour les dates
        - ✅ Structure basée sur le HTML réel d'Amazon France
        """)
    
    # Avertissement
    with st.expander("⚠️ Utilisation responsable", expanded=True):
        st.warning("""
        **Important :**
        - Respectez les conditions d'utilisation d'Amazon
        - Utilisez des pauses entre les requêtes
        - Ne surchargez pas les serveurs Amazon
        - Usage éducatif et de recherche uniquement
        """)
    
    # Mode de fonctionnement
    mode = st.radio(
        "🎯 Mode d'extraction:",
        ["🧪 Test URL unique", "📦 Traitement batch"],
        horizontal=True
    )
    
    if mode == "🧪 Test URL unique":
        st.subheader("🧪 Test avec une URL")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            product_url = st.text_input(
                "🔗 URL du produit Amazon:",
                placeholder="https://www.amazon.fr/dp/B086CYFSKW",
                value="https://www.amazon.fr/dp/B086CYFSKW",  # URL de test par défaut
                help="URL testée et validée"
            )
        
        with col2:
            max_pages = st.number_input(
                "📄 Pages max:",
                min_value=1,
                max_value=3,
                value=2,
                help="2 pages recommandées"
            )
        
        if st.button("🚀 Lancer le test", type="primary"):
            if product_url:
                with st.spinner("🔄 Extraction en cours..."):
                    urls = [product_url]
                    progress_bar = st.progress(0)
                    results = process_batch_urls(urls, max_pages, progress_bar)
                    
                    if results and any(r['commentaire_associe'] != "Aucun avis extrait" for r in results):
                        df = pd.DataFrame(results)
                        successful = df[df['commentaire_associe'] != "Aucun avis extrait"]
                        
                        st.success(f"🎉 **Test réussi!** {len(successful)} avis extraits")
                        
                        # Affichage des premiers résultats avec toutes les colonnes
                        st.subheader("📊 Aperçu des résultats")
                        # Colonnes principales pour l'affichage
                        display_cols = ['auteur', 'avis_notation', 'titre_avis', 'commentaire_associe', 'sentiment', 'achat_verifie']
                        st.dataframe(successful[display_cols].head(3), use_container_width=True)
                        
                        # Téléchargement complet
                        csv = df.to_csv(index=False, encoding='utf-8-sig')
                        st.download_button(
                            label="💾 Télécharger CSV complet",
                            data=csv,
                            file_name=f"test_avis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.error("❌ **Test échoué** - Aucun avis extrait")
            else:
                st.error("❌ Veuillez saisir une URL")
    
    else:
        # Mode batch
        st.subheader("📦 Traitement en batch")
        
        input_method = st.radio(
            "Saisie des URLs:",
            ["✍️ Saisie manuelle", "📁 Upload fichier"],
            horizontal=True
        )
        
        urls = []
        
        if input_method == "✍️ Saisie manuelle":
            urls_text = st.text_area(
                "🔗 URLs Amazon (une par ligne):",
                placeholder="https://www.amazon.fr/dp/B086CYFSKW\nhttps://www.amazon.fr/dp/B0DZP37N2P",
                height=120
            )
            if urls_text:
                urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        else:
            uploaded_file = st.file_uploader(
                "📁 Fichier texte (.txt)",
                type=['txt']
            )
            if uploaded_file:
                content = uploaded_file.read().decode('utf-8')
                urls = [url.strip() for url in content.split('\n') if url.strip()]
        
        if urls:
            st.info(f"📊 {len(urls)} URLs détectées")
            
            col1, col2 = st.columns(2)
            with col1:
                max_pages_batch = st.number_input(
                    "📄 Pages par produit:",
                    min_value=1,
                    max_value=2,
                    value=1,
                    help="1 page recommandée pour le batch"
                )
            
            with col2:
                limit_urls = st.number_input(
                    "🎯 Limiter à N URLs:",
                    min_value=0,
                    max_value=len(urls),
                    value=min(3, len(urls)),
                    help="Commencez petit"
                )
            
            # Aperçu
            with st.expander("👀 URLs à traiter"):
                display_urls = urls[:limit_urls] if limit_urls > 0 else urls
                for i, url in enumerate(display_urls, 1):
                    st.write(f"{i}. {url}")
                if limit_urls > 0 and limit_urls < len(urls):
                    st.write(f"... (+{len(urls) - limit_urls} autres)")
            
            # Estimation temps
            processing_urls = limit_urls if limit_urls > 0 else len(urls)
            estimated_minutes = processing_urls * max_pages_batch * 0.5  # 30 sec par page
            st.info(f"⏱️ Temps estimé: ~{estimated_minutes:.1f} minutes")
            
            if st.button("🚀 Lancer l'extraction batch", type="primary"):
                if limit_urls > 0:
                    urls = urls[:limit_urls]
                
                progress_bar = st.progress(0)
                results = process_batch_urls(urls, max_pages_batch, progress_bar)
                
                if results:
                    df = pd.DataFrame(results)
                    successful = df[df['commentaire_associe'] != "Aucun avis extrait"]
                    
                    # Statistiques
                    st.subheader("📊 Résultats")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("URLs traitées", len(df['url'].unique()))
                    with col2:
                        st.metric("URLs réussies", len(successful['url'].unique()))
                    with col3:
                        st.metric("Avis extraits", len(successful))
                    with col4:
                        if len(successful) > 0:
                            avg_rating = successful['avis_notation'].mean()
                            st.metric("Note moyenne", f"{avg_rating:.1f}/5" if pd.notna(avg_rating) else "N/A")
                    
                    # Sentiments
                    if len(successful) > 0:
                        st.subheader("📈 Sentiments")
                        sentiment_counts = successful['sentiment'].value_counts()
                        st.bar_chart(sentiment_counts)
                    
                    # Données
                    st.subheader("📋 Données complètes")
                    st.dataframe(df, use_container_width=True)
                    
                    # Export
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="💾 Télécharger CSV complet",
                        data=csv,
                        file_name=f"avis_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                    if len(successful) > 0:
                        st.success(f"✅ Extraction terminée! {len(successful)} avis sur {len(urls)} URLs")
                    else:
                        st.error("❌ Aucun avis extrait de toutes les URLs")

    # Documentation
    with st.expander("📖 Format de sortie CSV enrichi"):
        st.markdown("""
        **Colonnes disponibles dans le CSV :**
        - `url`: URL du produit Amazon
        - `nombre_avis`: Nombre total d'avis pour ce produit
        - `nombre_commentaires_client`: Nombre de commentaires extraits
        - `moyenne_avis`: Note moyenne du produit (sur 5)
        - `avis_notation`: Note de cet avis spécifique (1-5 étoiles)
        - `commentaire_associe`: Texte du commentaire client
        - `sentiment`: Analyse de sentiment (Positif/Négatif/Neutre)
        - `auteur`: Nom de l'auteur de l'avis
        - `date_avis`: Date de l'avis
        - `titre_avis`: Titre de l'avis
        - `achat_verifie`: True si achat vérifié
        - `votes_utiles`: Nombre de votes "utile"
        """)

if __name__ == "__main__":
    main()
