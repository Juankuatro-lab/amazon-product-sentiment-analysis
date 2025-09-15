import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin, urlparse
import random
from datetime import datetime
import json
from textblob import TextBlob
import io

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Extracteur d'avis Amazon - Batch",
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
            # Utilisation de TextBlob pour l'analyse de sentiment
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
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def extract_product_id(self, url):
        """Extrait l'ID du produit depuis l'URL Amazon"""
        try:
            patterns = [
                r'/dp/([A-Z0-9]{10})',
                r'/product/([A-Z0-9]{10})',
                r'asin=([A-Z0-9]{10})',
                r'/([A-Z0-9]{10})/'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            return None
        except:
            return None
    
    def get_reviews_url(self, product_url):
        """Construit l'URL de la page des avis"""
        product_id = self.extract_product_id(product_url)
        if not product_id:
            return None
        
        base_domain = "amazon.fr" if "amazon.fr" in product_url else "amazon.com"
        return f"https://www.{base_domain}/product-reviews/{product_id}/ref=cm_cr_dp_d_show_all_btm?sortBy=recent&pageNumber=1"
    
    def extract_product_info(self, product_url):
        """Extrait les informations générales du produit"""
        try:
            time.sleep(random.uniform(1, 3))
            response = requests.get(product_url, headers=self.headers, timeout=10)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraction de la note moyenne
            avg_rating = None
            rating_elem = soup.find('span', class_='a-icon-alt')
            if rating_elem:
                rating_text = rating_elem.text
                rating_match = re.search(r'(\d+(?:,\d+)?)', rating_text)
                if rating_match:
                    avg_rating = float(rating_match.group(1).replace(',', '.'))
            
            # Extraction du nombre total d'avis
            total_reviews = 0
            reviews_elem = soup.find('span', {'data-hook': 'total-review-count'}) or \
                          soup.find('a', {'data-hook': 'see-all-reviews-link-foot'})
            
            if reviews_elem:
                reviews_text = reviews_elem.text
                reviews_match = re.search(r'(\d+(?:\s?\d+)*)', reviews_text.replace(',', '').replace(' ', ''))
                if reviews_match:
                    total_reviews = int(reviews_match.group(1))
            
            return {
                'avg_rating': avg_rating,
                'total_reviews': total_reviews
            }
            
        except Exception as e:
            st.warning(f"Erreur lors de l'extraction des infos produit: {str(e)}")
            return None
    
    def extract_single_review(self, review_element):
        """Extrait les informations d'un seul avis"""
        try:
            review_data = {}
            
            # Note (étoiles)
            rating_elem = review_element.find('span', class_='a-icon-alt')
            if rating_elem:
                rating_text = rating_elem.text
                rating_match = re.search(r'(\d+(?:,\d+)?)', rating_text)
                review_data['rating'] = float(rating_match.group(1).replace(',', '.')) if rating_match else None
            else:
                review_data['rating'] = None
            
            # Contenu de l'avis
            content_elem = review_element.find('span', {'data-hook': 'review-body'})
            review_data['content'] = content_elem.text.strip() if content_elem else ""
            
            return review_data
            
        except Exception as e:
            return None
    
    def extract_reviews_for_product(self, product_url, max_pages=3):
        """Extrait les avis d'un produit spécifique"""
        try:
            # Extraction des informations générales du produit
            product_info = self.extract_product_info(product_url)
            
            reviews = []
            reviews_url = self.get_reviews_url(product_url)
            
            if not reviews_url:
                return None
            
            # Extraction des avis détaillés
            for page in range(1, max_pages + 1):
                try:
                    current_url = reviews_url.replace('pageNumber=1', f'pageNumber={page}')
                    time.sleep(random.uniform(2, 4))
                    
                    response = requests.get(current_url, headers=self.headers, timeout=10)
                    
                    if response.status_code != 200:
                        continue
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    review_elements = soup.find_all('div', {'data-hook': 'review'})
                    
                    if not review_elements:
                        break
                    
                    for review_element in review_elements:
                        review_data = self.extract_single_review(review_element)
                        if review_data and review_data['content']:
                            reviews.append(review_data)
                    
                    # Vérifier s'il y a une page suivante
                    next_page = soup.find('li', class_='a-last')
                    if not next_page or 'a-disabled' in next_page.get('class', []):
                        break
                        
                except Exception as e:
                    continue
            
            return {
                'product_info': product_info,
                'reviews': reviews
            }
            
        except Exception as e:
            st.error(f"Erreur lors de l'extraction pour {product_url}: {str(e)}")
            return None

def process_batch_urls(urls, max_pages_per_product=3, progress_placeholder=None):
    """Traite une liste d'URLs en batch"""
    extractor = AmazonReviewsExtractor()
    analyzer = SentimentAnalyzer()
    results = []
    
    total_urls = len(urls)
    
    for i, url in enumerate(urls):
        if progress_placeholder:
            progress_placeholder.progress((i + 1) / total_urls)
            
        st.write(f"🔄 Traitement de l'URL {i+1}/{total_urls}: {url[:50]}...")
        
        # Extraction des données pour ce produit
        product_data = extractor.extract_reviews_for_product(url.strip(), max_pages_per_product)
        
        if product_data and product_data['reviews']:
            product_info = product_data['product_info'] or {}
            reviews = product_data['reviews']
            
            # Calcul des statistiques
            total_reviews = product_info.get('total_reviews', len(reviews))
            avg_rating = product_info.get('avg_rating')
            if not avg_rating and reviews:
                # Calcul de la moyenne sur les avis extraits
                ratings = [r['rating'] for r in reviews if r['rating'] is not None]
                avg_rating = sum(ratings) / len(ratings) if ratings else None
            
            # Création d'une ligne par avis
            for review in reviews:
                if review['content']:  # Seulement les avis avec commentaire
                    sentiment = analyzer.analyze_sentiment(review['content'])
                    
                    results.append({
                        'url': url.strip(),
                        'nombre_avis': total_reviews,
                        'nombre_commentaires_client': len(reviews),
                        'moyenne_avis': round(avg_rating, 1) if avg_rating else None,
                        'avis_notation': review['rating'],
                        'commentaire_associe': review['content'],
                        'sentiment': sentiment
                    })
            
            st.success(f"✅ {len(reviews)} avis extraits pour cette URL")
        else:
            st.warning(f"⚠️ Aucun avis extrait pour: {url}")
            # Ajouter une ligne vide pour cette URL
            results.append({
                'url': url.strip(),
                'nombre_avis': 0,
                'nombre_commentaires_client': 0,
                'moyenne_avis': None,
                'avis_notation': None,
                'commentaire_associe': "Aucun avis extrait",
                'sentiment': "N/A"
            })
    
    return results

def main():
    st.title("📝 Extracteur d'avis Amazon - Traitement en Batch")
    st.markdown("---")
    
    # Avertissement légal
    with st.expander("⚠️ Avertissement important", expanded=True):
        st.warning("""
        **Utilisation responsable uniquement:**
        - Cet outil est destiné à un usage éducatif et de recherche
        - Respectez les conditions d'utilisation d'Amazon
        - Le traitement en batch peut prendre beaucoup de temps
        - Utilisez avec modération pour éviter d'être bloqué
        """)
    
    # Choix du mode
    mode = st.radio(
        "🎯 Mode d'extraction:",
        ["URL unique", "Traitement en batch (plusieurs URLs)"],
        horizontal=True
    )
    
    if mode == "URL unique":
        # Mode URL unique (existant)
        col1, col2 = st.columns([2, 1])
        
        with col1:
            product_url = st.text_input(
                "🔗 URL du produit Amazon:",
                placeholder="https://www.amazon.fr/dp/XXXXXXXXXX"
            )
        
        with col2:
            max_pages = st.number_input(
                "📄 Nombre de pages max:",
                min_value=1,
                max_value=10,
                value=3
            )
        
        if st.button("🚀 Extraire les avis", type="primary"):
            if product_url:
                urls = [product_url]
                progress_bar = st.progress(0)
                results = process_batch_urls(urls, max_pages, progress_bar)
                
                if results:
                    df = pd.DataFrame(results)
                    st.success(f"🎉 {len(results)} avis extraits!")
                    st.dataframe(df)
                    
                    # Téléchargement CSV
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="💾 Télécharger CSV",
                        data=csv,
                        file_name=f"avis_amazon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
    
    else:
        # Mode batch
        st.subheader("📋 Traitement en batch")
        
        # Options de saisie
        input_method = st.radio(
            "Mode de saisie des URLs:",
            ["Saisie manuelle", "Upload fichier texte"],
            horizontal=True
        )
        
        urls = []
        
        if input_method == "Saisie manuelle":
            urls_text = st.text_area(
                "🔗 URLs des produits Amazon (une par ligne):",
                placeholder="https://www.amazon.fr/dp/XXXXXXXXXX\nhttps://www.amazon.fr/dp/YYYYYYYYYY\n...",
                height=150
            )
            if urls_text:
                urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        else:
            uploaded_file = st.file_uploader(
                "📁 Fichier texte avec les URLs (une par ligne)",
                type=['txt']
            )
            if uploaded_file:
                content = uploaded_file.read().decode('utf-8')
                urls = [url.strip() for url in content.split('\n') if url.strip()]
        
        if urls:
            st.info(f"📊 {len(urls)} URLs détectées")
            
            # Options pour le batch
            col1, col2 = st.columns(2)
            with col1:
                max_pages_batch = st.number_input(
                    "📄 Pages max par produit:",
                    min_value=1,
                    max_value=5,
                    value=2,
                    help="Moins de pages = traitement plus rapide"
                )
            
            with col2:
                sample_urls = st.number_input(
                    "🎯 Limiter à N URLs (0 = toutes):",
                    min_value=0,
                    max_value=len(urls),
                    value=0 if len(urls) <= 10 else 10
                )
            
            # Aperçu des URLs
            with st.expander("👀 Aperçu des URLs à traiter"):
                display_urls = urls[:sample_urls] if sample_urls > 0 else urls
                for i, url in enumerate(display_urls, 1):
                    st.write(f"{i}. {url}")
                if sample_urls > 0 and sample_urls < len(urls):
                    st.write(f"... et {len(urls) - sample_urls} autres URLs")
            
            # Estimation du temps
            estimated_time = len(display_urls if sample_urls > 0 else urls) * max_pages_batch * 10  # ~10 sec par page
            st.info(f"⏱️ Temps estimé: ~{estimated_time//60} minutes {estimated_time%60} secondes")
            
            if st.button("🚀 Lancer l'extraction en batch", type="primary"):
                if sample_urls > 0:
                    urls = urls[:sample_urls]
                
                with st.spinner("🔄 Traitement en cours..."):
                    progress_bar = st.progress(0)
                    results = process_batch_urls(urls, max_pages_batch, progress_bar)
                
                if results:
                    df = pd.DataFrame(results)
                    
                    # Statistiques globales
                    st.subheader("📊 Résultats du traitement batch")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("URLs traitées", len(df['url'].unique()))
                    with col2:
                        st.metric("Total avis", len(df))
                    with col3:
                        avg_sentiment = df['sentiment'].value_counts()
                        most_common = avg_sentiment.index[0] if len(avg_sentiment) > 0 else "N/A"
                        st.metric("Sentiment dominant", most_common)
                    with col4:
                        avg_rating = df['avis_notation'].mean()
                        st.metric("Note moyenne", f"{avg_rating:.1f}/5" if pd.notna(avg_rating) else "N/A")
                    
                    # Répartition des sentiments
                    if not df.empty:
                        st.subheader("📈 Répartition des sentiments")
                        sentiment_counts = df['sentiment'].value_counts()
                        st.bar_chart(sentiment_counts)
                    
                    # Affichage des données
                    st.subheader("📋 Données extraites")
                    st.dataframe(df, use_container_width=True)
                    
                    # Téléchargement
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="💾 Télécharger CSV complet",
                        data=csv,
                        file_name=f"avis_amazon_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                    st.success(f"✅ Traitement terminé! {len(results)} avis extraits au total")
                else:
                    st.error("❌ Aucun avis n'a pu être extrait")

    # Instructions
    with st.expander("📖 Format de sortie CSV"):
        st.markdown("""
        **Colonnes du fichier CSV exporté:**
        - `url`: URL du produit Amazon
        - `nombre_avis`: Nombre total d'avis pour ce produit
        - `nombre_commentaires_client`: Nombre de commentaires extraits
        - `moyenne_avis`: Note moyenne du produit (sur 5)
        - `avis_notation`: Note de cet avis spécifique (1-5 étoiles)
        - `commentaire_associe`: Texte du commentaire client
        - `sentiment`: Analyse de sentiment (Positif/Négatif/Neutre)
        
        **Note:** Il y a une ligne par avis/commentaire extrait.
        """)
    
    with st.expander("🔧 Installation des dépendances"):
        st.code("""
pip install streamlit requests beautifulsoup4 pandas textblob

# Pour l'analyse de sentiment en français (optionnel):
python -m textblob.download_corpora
        """, language="bash")

if __name__ == "__main__":
    main()
