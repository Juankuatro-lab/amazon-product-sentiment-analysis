import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import pandas as pd
import time
import random
import requests
from datetime import datetime
from textblob import TextBlob
import json

# Configuration Streamlit
st.set_page_config(
    page_title="Amazon Scraper - Selenium Advanced",
    page_icon="🤖",
    layout="wide"
)

class ProxyRotator:
    """Gestionnaire de proxies rotatifs"""
    
    def __init__(self):
        # Liste de proxies gratuits (à remplacer par vos proxies premium)
        self.free_proxies = []
        self.premium_proxies = []
        self.current_proxy_index = 0
        
    def get_free_proxies(self):
        """Récupère une liste de proxies gratuits (instables)"""
        try:
            # API gratuite pour récupérer des proxies
            response = requests.get("https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&format=json")
            if response.status_code == 200:
                proxies = response.json()
                self.free_proxies = [f"{p['ip']}:{p['port']}" for p in proxies[:10]]
                return self.free_proxies
        except:
            pass
        
        # Proxies de fallback (peuvent ne pas fonctionner)
        self.free_proxies = [
            "8.210.83.33:80",
            "47.251.5.248:80",
            "47.88.3.19:8080"
        ]
        return self.free_proxies
    
    def get_next_proxy(self):
        """Retourne le prochain proxy à utiliser"""
        if not self.free_proxies:
            self.get_free_proxies()
        
        if self.free_proxies:
            proxy = self.free_proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.free_proxies)
            return proxy
        return None

class AdvancedAmazonScraper:
    """Scraper Amazon avec Selenium et anti-détection"""
    
    def __init__(self, use_proxies=False):
        self.use_proxies = use_proxies
        self.proxy_rotator = ProxyRotator() if use_proxies else None
        self.driver = None
        
    def create_driver(self, proxy=None):
        """Crée un driver Selenium avec options anti-détection"""
        chrome_options = Options()
        
        # Options anti-détection
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User agent aléatoire
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        # Proxy si disponible
        if proxy:
            chrome_options.add_argument(f"--proxy-server=http://{proxy}")
            st.info(f"🔄 Utilisation du proxy: {proxy}")
        
        # Mode headless optionnel
        # chrome_options.add_argument("--headless")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Script anti-détection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return True
        except Exception as e:
            st.error(f"❌ Erreur création driver: {str(e)}")
            return False
    
    def human_like_delay(self, min_seconds=2, max_seconds=5):
        """Pause aléatoire pour imiter un humain"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def scroll_page(self):
        """Scroll naturel de la page"""
        total_height = self.driver.execute_script("return document.body.scrollHeight")
        for i in range(1, 4):
            self.driver.execute_script(f"window.scrollTo(0, {total_height * i / 4});")
            time.sleep(random.uniform(0.5, 1.5))
    
    def extract_reviews_selenium(self, product_url, max_pages=2):
        """Extrait les avis en utilisant Selenium"""
        reviews = []
        
        try:
            # Créer le driver
            proxy = self.proxy_rotator.get_next_proxy() if self.use_proxies else None
            if not self.create_driver(proxy):
                return reviews
            
            # Aller sur la page produit
            st.write(f"🌐 Chargement de la page: {product_url}")
            self.driver.get(product_url)
            self.human_like_delay(3, 6)
            
            # Chercher le lien "Voir tous les avis"
            try:
                # Plusieurs sélecteurs possibles pour le lien des avis
                review_link_selectors = [
                    "a[data-hook='see-all-reviews-link-foot']",
                    "a[href*='product-reviews']",
                    "#acrCustomerReviewText",
                    ".a-link-emphasis[href*='product-reviews']"
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
                    st.success(f"✅ Lien des avis trouvé: {reviews_url[:60]}...")
                    
                    # Aller sur la page des avis
                    self.driver.get(reviews_url)
                    self.human_like_delay(3, 6)
                else:
                    st.warning("⚠️ Lien des avis non trouvé, tentative d'extraction sur la page produit")
                
            except Exception as e:
                st.warning(f"⚠️ Erreur recherche lien avis: {str(e)}")
            
            # Extraire les avis de chaque page
            for page in range(1, max_pages + 1):
                st.write(f"📖 Extraction page {page}...")
                
                # Scroll pour charger le contenu
                self.scroll_page()
                self.human_like_delay(2, 4)
                
                # Attendre que les avis se chargent
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-hook='review']"))
                    )
                except TimeoutException:
                    st.warning(f"⚠️ Timeout sur la page {page}")
                    continue
                
                # Extraire les avis de la page courante
                page_reviews = self.extract_reviews_from_current_page()
                reviews.extend(page_reviews)
                
                st.success(f"✅ Page {page}: {len(page_reviews)} avis extraits")
                
                # Aller à la page suivante
                if page < max_pages:
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, "li.a-last:not(.a-disabled) a")
                        next_button.click()
                        self.human_like_delay(3, 6)
                    except:
                        st.info("📄 Pas de page suivante")
                        break
            
        except Exception as e:
            st.error(f"❌ Erreur Selenium: {str(e)}")
        
        finally:
            if self.driver:
                self.driver.quit()
        
        return reviews
    
    def extract_reviews_from_current_page(self):
        """Extrait les avis de la page courante"""
        reviews = []
        
        try:
            # Trouver tous les éléments d'avis
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
                    
                    # Ajouter si contenu valide
                    if review_data.get('content') and len(review_data['content']) > 10:
                        reviews.append(review_data)
                
                except Exception as e:
                    continue
        
        except Exception as e:
            st.error(f"❌ Erreur extraction page: {str(e)}")
        
        return reviews

def main():
    st.title("🤖 Amazon Scraper - Selenium + Anti-détection")
    st.markdown("---")
    
    # Avertissements
    with st.expander("⚠️ Prérequis et avertissements", expanded=True):
        st.warning("""
        **Installation requise:**
        ```bash
        pip install selenium webdriver-manager
        # Installer ChromeDriver automatiquement
        ```
        
        **Avertissements:**
        - Selenium ouvre un navigateur visible (plus lent que requests)
        - Les proxies gratuits sont instables
        - Amazon peut toujours détecter l'automatisation
        - Usage éducatif uniquement
        """)
    
    # Configuration
    st.subheader("🔧 Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        use_proxies = st.checkbox(
            "🔄 Utiliser des proxies rotatifs",
            help="Proxies gratuits (instables) pour éviter les blocages"
        )
    
    with col2:
        max_pages = st.number_input(
            "📄 Pages max par produit:",
            min_value=1,
            max_value=3,
            value=1,
            help="Selenium est plus lent"
        )
    
    # Test URL
    st.subheader("🧪 Test avec Selenium")
    
    product_url = st.text_input(
        "🔗 URL du produit Amazon:",
        value="https://www.amazon.fr/dp/B086CYFSKW",
        help="URL pour tester l'extraction Selenium"
    )
    
    if st.button("🚀 Lancer l'extraction Selenium", type="primary"):
        if product_url:
            scraper = AdvancedAmazonScraper(use_proxies=use_proxies)
            
            with st.spinner("🤖 Selenium en cours..."):
                reviews = scraper.extract_reviews_selenium(product_url, max_pages)
            
            if reviews:
                st.success(f"🎉 {len(reviews)} avis extraits avec Selenium!")
                
                # Traitement des données
                for review in reviews:
                    blob = TextBlob(review.get('content', ''))
                    polarity = blob.sentiment.polarity
                    if polarity > 0.1:
                        review['sentiment'] = "Positif"
                    elif polarity < -0.1:
                        review['sentiment'] = "Négatif"
                    else:
                        review['sentiment'] = "Neutre"
                
                # Affichage
                df = pd.DataFrame(reviews)
                st.dataframe(df, use_container_width=True)
                
                # Export
                csv = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="💾 Télécharger CSV",
                    data=csv,
                    file_name=f"selenium_avis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.error("❌ Aucun avis extrait avec Selenium")
        else:
            st.error("❌ Veuillez saisir une URL")
    
    # Informations techniques
    with st.expander("🔧 Informations techniques Selenium"):
        st.markdown("""
        **Avantages:**
        - Navigateur réel (plus difficile à détecter)
        - JavaScript exécuté naturellement
        - Interaction humaine simulée
        
        **Inconvénients:**
        - Plus lent (10-30 secondes par page)
        - Consomme plus de ressources
        - Nécessite ChromeDriver
        
        **Anti-détection:**
        - User-agents rotatifs
        - Délais aléatoires humains
        - Scroll naturel
        - Suppression des marqueurs webdriver
        """)

if __name__ == "__main__":
    main()
