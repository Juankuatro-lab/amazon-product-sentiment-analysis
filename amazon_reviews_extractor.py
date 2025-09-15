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

# Imports pour Selenium avec gestion automatique
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
    import undetected_chromedriver as uc
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Configuration Streamlit
st.set_page_config(
    page_title="Amazon Reviews Scraper - Version Finale",
    page_icon="🔧",
    layout="wide"
)

class SentimentAnalyzer:
    """Analyseur de sentiment pour les commentaires"""
    
    @staticmethod
    def analyze_sentiment(text):
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

class BasicAmazonScraper:
    """Scraper de base avec requests/BeautifulSoup amélioré"""
    
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        self.session.headers.update(self.headers)
    
    def clean_url(self, url):
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
                if "amazon.fr" in url:
                    domain = "amazon.fr"
                elif "amazon.com" in url:
                    domain = "amazon.com"
                elif "amazon.de" in url:
                    domain = "amazon.de"
                elif "amazon.co.uk" in url:
                    domain = "amazon.co.uk"
                else:
                    domain = "amazon.fr"
                
                clean_product_url = f"https://www.{domain}/dp/{asin}"
                return clean_product_url, asin, domain
        
        return None, None, None
    
    def extract_reviews_basic(self, product_url, max_pages=2):
        reviews = []
        
        clean_url, asin, domain = self.clean_url(product_url)
        if not clean_url or not asin:
            st.error("Impossible d'extraire l'ASIN depuis l'URL")
            return reviews
        
        st.info(f"URL nettoyée: {clean_url}")
        st.info(f"ASIN: {asin} | Domaine: {domain}")
        
        # Construire l'URL des avis
        reviews_base_url = f"https://www.{domain}/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews&sortBy=recent&pageNumber=1"
        
        for page in range(1, max_pages + 1):
            try:
                current_url = reviews_base_url.replace('pageNumber=1', f'pageNumber={page}')
                st.write(f"Extraction page {page}: {current_url[:80]}...")
                
                time.sleep(random.uniform(3, 6))
                
                response = self.session.get(current_url, timeout=15)
                
                if response.status_code != 200:
                    st.warning(f"HTTP {response.status_code} pour la page {page}")
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                review_elements = soup.select('li[data-hook="review"]')
                
                if not review_elements:
                    st.warning(f"Aucun avis trouvé sur la page {page}")
                    break
                
                page_reviews = 0
                for review_element in review_elements:
                    review_data = self.extract_single_review(review_element)
                    if review_data and review_data.get('content'):
                        reviews.append(review_data)
                        page_reviews += 1
                
                st.success(f"Page {page}: {page_reviews} avis extraits")
                
                if page_reviews == 0:
                    break
                
                next_disabled = soup.select_one('li.a-disabled.a-last')
                if next_disabled:
                    st.info("Dernière page atteinte")
                    break
                    
            except Exception as e:
                st.error(f"Erreur page {page}: {str(e)}")
                continue
        
        return reviews
    
    def extract_single_review(self, review_element):
        try:
            review_data = {}
            
            # Note
            rating = None
            rating_elem = review_element.select_one('i[data-hook="review-star-rating"] span.a-icon-alt')
            if rating_elem:
                rating_text = rating_elem.text
                rating_match = re.search(r'(\d+(?:,\d+)?)', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1).replace(',', '.'))
            review_data['rating'] = rating
            
            # Contenu
            content = ""
            content_elem = review_element.select_one('span[data-hook="review-body"]')
            if content_elem:
                for script in content_elem(["script", "style"]):
                    script.decompose()
                content = content_elem.get_text(separator=' ', strip=True)
                content = re.sub(r'En savoir plus.*$', '', content)
                content = re.sub(r'Lire la suite.*$', '', content)
                content = content.strip()
            review_data['content'] = content
            
            # Auteur
            author = ""
            author_elem = review_element.select_one('span.a-profile-name')
            if author_elem:
                author = author_elem.get_text(strip=True)
            review_data['author'] = author
            
            # Date
            date = ""
            date_elem = review_element.select_one('span[data-hook="review-date"]')
            if date_elem:
                date = date_elem.get_text(strip=True)
            review_data['date'] = date
            
            # Titre
            title = ""
            title_elem = review_element.select_one('a[data-hook="review-title"] span')
            if title_elem:
                title = title_elem.get_text(strip=True)
            review_data['title'] = title
            
            # Achat vérifié
            verified = False
            verified_elem = review_element.select_one('span[data-hook="avp-badge-linkless"]')
            if verified_elem and "vérifié" in verified_elem.text.lower():
                verified = True
            review_data['verified_purchase'] = verified
            
            # Votes utiles
            helpful_votes = 0
            helpful_elem = review_element.select_one('span[data-hook="helpful-vote-statement"]')
            if helpful_elem:
                helpful_text = helpful_elem.text
                helpful_match = re.search(r'(\d+)', helpful_text)
                if helpful_match:
                    helpful_votes = int(helpful_match.group(1))
            review_data['helpful_votes'] = helpful_votes
            
            return review_data if (rating is not None or (content and len(content) > 10)) else None
            
        except Exception as e:
            return None

class AdvancedSeleniumScraper:
    """Scraper Selenium avec gestion automatique des drivers"""
    
    def __init__(self):
        self.driver = None
    
    def create_driver_auto(self):
        """Crée un driver avec installation automatique"""
        try:
            # Méthode 1: undetected-chromedriver (recommandé)
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
            options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            self.driver = uc.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return True
            
        except Exception as e1:
            st.warning(f"Échec undetected-chromedriver: {str(e1)}")
            
            try:
                # Méthode 2: webdriver-manager
                options = Options()
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                return True
                
            except Exception as e2:
                st.error(f"Échec webdriver-manager: {str(e2)}")
                return False
    
    def extract_reviews_selenium(self, product_url, max_pages=2):
        reviews = []
        
        if not self.create_driver_auto():
            st.error("Impossible de créer le driver Selenium")
            return reviews
        
        try:
            st.write(f"Selenium: Navigation vers {product_url}")
            self.driver.get(product_url)
            time.sleep(random.uniform(3, 6))
            
            # Chercher le lien des avis
            review_link_selectors = [
                "a[data-hook='see-all-reviews-link-foot']",
                "a[href*='product-reviews']",
                "#acrCustomerReviewText"
            ]
            
            review_link = None
            for selector in review_link_selectors:
                try:
                    review_link = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if review_link:
                reviews_url = review_link.get_attribute('href')
                st.success(f"Lien des avis trouvé: {reviews_url[:60]}...")
                self.driver.get(reviews_url)
                time.sleep(random.uniform(3, 6))
            
            # Extraire les avis de chaque page
            for page in range(1, max_pages + 1):
                st.write(f"Selenium - Page {page}...")
                
                # Scroll pour charger le contenu
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(2)
                
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-hook='review']"))
                    )
                except TimeoutException:
                    st.warning(f"Timeout sur la page {page}")
                    continue
                
                page_reviews = self.extract_reviews_from_current_page()
                reviews.extend(page_reviews)
                
                st.success(f"Page {page}: {len(page_reviews)} avis extraits")
                
                # Page suivante
                if page < max_pages:
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, "li.a-last:not(.a-disabled) a")
                        next_button.click()
                        time.sleep(random.uniform(3, 6))
                    except:
                        st.info("Pas de page suivante")
                        break
            
        except Exception as e:
            st.error(f"Erreur Selenium: {str(e)}")
        
        finally:
            if self.driver:
                self.driver.quit()
        
        return reviews
    
    def extract_reviews_from_current_page(self):
        reviews = []
        
        try:
            review_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-hook='review']")
            
            for element in review_elements:
                try:
                    review_data = {}
                    
                    # Note
                    try:
                        rating_elem = element.find_element(By.CSS_SELECTOR, "i[data-hook='review-star-rating'] span.a-icon-alt")
                        rating_text = rating_elem.text
                        rating_match = re.search(r'(\d+(?:,\d+)?)', rating_text)
                        if rating_match:
                            review_data['rating'] = float(rating_match.group(1).replace(',', '.'))
                    except:
                        review_data['rating'] = None
                    
                    # Contenu
                    try:
                        content_elem = element.find_element(By.CSS_SELECTOR, "span[data-hook='review-body']")
                        review_data['content'] = content_elem.text.strip()
                    except:
                        review_data['content'] = ""
                    
                    # Auteur
                    try:
                        author_elem = element.find_element(By.CSS_SELECTOR, "span.a-profile-name")
                        review_data['author'] = author_elem.text.strip()
                    except:
                        review_data['author'] = ""
                    
                    # Date
                    try:
                        date_elem = element.find_element(By.CSS_SELECTOR, "span[data-hook='review-date']")
                        review_data['date'] = date_elem.text.strip()
                    except:
                        review_data['date'] = ""
                    
                    # Titre
                    try:
                        title_elem = element.find_element(By.CSS_SELECTOR, "a[data-hook='review-title'] span")
                        review_data['title'] = title_elem.text.strip()
                    except:
                        review_data['title'] = ""
                    
                    # Achat vérifié
                    try:
                        verified_elem = element.find_element(By.CSS_SELECTOR, "span[data-hook='avp-badge-linkless']")
                        review_data['verified_purchase'] = "vérifié" in verified_elem.text.lower()
                    except:
                        review_data['verified_purchase'] = False
                    
                    # Votes utiles
                    try:
                        helpful_elem = element.find_element(By.CSS_SELECTOR, "span[data-hook='helpful-vote-statement']")
                        helpful_text = helpful_elem.text
                        helpful_match = re.search(r'(\d+)', helpful_text)
                        review_data['helpful_votes'] = int(helpful_match.group(1)) if helpful_match else 0
                    except:
                        review_data['helpful_votes'] = 0
                    
                    if review_data.get('content') and len(review_data['content']) > 10:
                        reviews.append(review_data)
                
                except Exception as e:
                    continue
        
        except Exception as e:
            st.error(f"Erreur extraction page: {str(e)}")
        
        return reviews

def process_urls(urls, method, max_pages, progress_placeholder=None):
    """Traite une liste d'URLs avec la méthode choisie"""
    analyzer = SentimentAnalyzer()
    results = []
    
    total_urls = len(urls)
    
    for i, url in enumerate(urls):
        if progress_placeholder:
            progress_placeholder.progress((i + 1) / total_urls)
        
        st.subheader(f"URL {i+1}/{total_urls}")
        st.write(f"**URL:** {url}")
        
        # Choisir la méthode d'extraction
        reviews = []
        if method == "Requests + BeautifulSoup":
            scraper = BasicAmazonScraper()
            reviews = scraper.extract_reviews_basic(url.strip(), max_pages)
        elif method == "Selenium" and SELENIUM_AVAILABLE:
            scraper = AdvancedSeleniumScraper()
            reviews = scraper.extract_reviews_selenium(url.strip(), max_pages)
        else:
            st.error("Méthode non disponible ou bibliothèques manquantes")
            continue
        
        if reviews:
            # Calculer les statistiques
            total_reviews = len(reviews)
            avg_rating = None
            ratings = [r['rating'] for r in reviews if r['rating'] is not None]
            if ratings:
                avg_rating = sum(ratings) / len(ratings)
            
            # Créer une ligne par avis avec analyse de sentiment
            for review in reviews:
                if review.get('content'):
                    sentiment = analyzer.analyze_sentiment(review['content'])
                    
                    results.append({
                        'url': url.strip(),
                        'nombre_avis': total_reviews,
                        'nombre_commentaires_client': total_reviews,
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
            
            st.success(f"Succès: {len(reviews)} avis extraits!")
        else:
            st.error("Échec: Aucun avis extrait")
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
    st.title("Amazon Reviews Scraper - Version Finale")
    st.markdown("---")
    
    # Vérification des dépendances
    with st.expander("Statut des dépendances", expanded=False):
        st.write("Requests + BeautifulSoup:", "✅ Disponible")
        st.write("Selenium:", "✅ Disponible" if SELENIUM_AVAILABLE else "❌ Non disponible")
        
        if not SELENIUM_AVAILABLE:
            st.code("""
pip install selenium webdriver-manager undetected-chromedriver
            """)
    
    # Configuration
    st.subheader("Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        method = st.selectbox(
            "Méthode d'extraction:",
            ["Requests + BeautifulSoup", "Selenium"] if SELENIUM_AVAILABLE else ["Requests + BeautifulSoup"],
            help="Selenium plus efficace mais nécessite installation"
        )
    
    with col2:
        max_pages = st.number_input(
            "Pages max par produit:",
            min_value=1,
            max_value=5,
            value=2,
            help="Plus de pages = plus lent"
        )
    
    # Mode d'utilisation
    mode = st.radio(
        "Mode d'utilisation:",
        ["URL unique", "Batch (plusieurs URLs)"],
        horizontal=True
    )
    
    if mode == "URL unique":
        # Mode URL unique
        st.subheader("Test URL unique")
        
        product_url = st.text_input(
            "URL du produit Amazon:",
            value="https://www.amazon.fr/dp/B086CYFSKW",
            help="URL complète du produit Amazon"
        )
        
        if st.button("Extraire les avis", type="primary"):
            if product_url:
                progress_bar = st.progress(0)
                results = process_urls([product_url], method, max_pages, progress_bar)
                
                if results and any(r['commentaire_associe'] != "Aucun avis extrait" for r in results):
                    df = pd.DataFrame(results)
                    successful = df[df['commentaire_associe'] != "Aucun avis extrait"]
                    
                    st.success(f"Extraction réussie! {len(successful)} avis extraits")
                    
                    # Affichage
                    st.subheader("Résultats")
                    display_cols = ['auteur', 'avis_notation', 'titre_avis', 'commentaire_associe', 'sentiment']
                    st.dataframe(successful[display_cols].head(5), use_container_width=True)
                    
                    # Export
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="Télécharger CSV",
                        data=csv,
                        file_name=f"avis_amazon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.error("Extraction échouée - Aucun avis extrait")
            else:
                st.error("Veuillez saisir une URL")
    
    else:
        # Mode batch
        st.subheader("Traitement en batch")
        
        input_method = st.radio(
            "Saisie des URLs:",
            ["Saisie manuelle", "Upload fichier"],
            horizontal=True
        )
        
        urls = []
        
        if input_method == "Saisie manuelle":
            urls_text = st.text_area(
                "URLs Amazon (une par ligne):",
                placeholder="https://www.amazon.fr/dp/B086CYFSKW\nhttps://www.amazon.fr/dp/B0DZP37N2P",
                height=120
            )
            if urls_text:
                urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        else:
            uploaded_file = st.file_uploader("Fichier texte (.txt)", type=['txt'])
            if uploaded_file:
                content = uploaded_file.read().decode('utf-8')
                urls = [url.strip() for url in content.split('\n') if url.strip()]
        
        if urls:
            st.info(f"{len(urls)} URLs détectées")
            
            col1, col2 = st.columns(2)
            with col1:
                limit_urls = st.number_input(
                    "Limiter à N URLs (0 = toutes):",
                    min_value=0,
                    max_value=len(urls),
                    value=min(3, len(urls)),
                    help="Commencez avec peu d'URLs"
                )
            
            with col2:
                estimated_time = (limit_urls if limit_urls > 0 else len(urls)) * max_pages * 30
                st.info(f"Temps estimé: ~{estimated_time//60} minutes")
            
            with st.expander("URLs à traiter"):
                display_urls = urls[:limit_urls] if limit_urls > 0 else urls
                for i, url in enumerate(display_urls, 1):
                    st.write(f"{i}. {url}")
            
            if st.button("Lancer l'extraction batch", type="primary"):
                if limit_urls > 0:
                    urls = urls[:limit_urls]
                
                progress_bar = st.progress(0)
                results = process_urls(urls, method, max_pages, progress_bar)
                
                if results:
                    df = pd.DataFrame(results)
                    successful = df[df['commentaire_associe'] != "Aucun avis extrait"]
                    
                    st.subheader("Résultats batch")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("URLs traitées", len(df['url'].unique()))
                    with col2:
                        st.metric("URLs réussies", len(successful['url'].unique()))
                    with col3:
                        st.metric("Total avis", len(successful))
                    with col4:
                        if len(successful) > 0:
                            avg_rating = successful['avis_notation'].mean()
                            st.metric("Note moyenne", f"{avg_rating:.1f}/5" if pd.notna(avg_rating) else "N/A")
                    
                    if len(successful) > 0:
                        st.subheader("Répartition des sentiments")
                        sentiment_counts = successful['sentiment'].value_counts()
                        st.bar_chart(sentiment_counts)
                    
                    st.subheader("Données complètes")
                    st.dataframe(df, use_container_width=True)
                    
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="Télécharger CSV complet",
                        data=csv,
                        file_name=f"avis_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                    if len(successful) > 0:
                        st.success(f"Traitement terminé! {len(successful)} avis extraits")
                    else:
                        st.error("Aucun avis extrait de toutes les URLs")

if __name__ == "__main__":
    main()
