import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

class SkyMoviesScraper:
    def __init__(self):
        self.base_url = "https://skymovieshd.mba"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Cloud hosting providers for direct links
        self.cloud_hosts = {
            'gofile': ['gofile.io'],
            'streamtape': ['streamtape.to'],
            'terabox': ['terabox.com', '1024tera.com'],
            'gdrive': ['drive.google.com'],
            'mediafire': ['mediafire.com'],
            'mega': ['mega.nz'],
            'pixeldrain': ['pixeldrain.com'],
            'vikingfile': ['vikingfile.com'],
            'gdflix': ['gdflix.dev', 'gdflix.'],
            'hubdrive': ['hubdrive.'],
            'filepress': ['filepress.'],
            'appdrive': ['appdrive.']
        }
    
    async def search_movies(self, query):
        """Search movies with improved parsing"""
        try:
            search_url = f"{self.base_url}/search.php?search={query.replace(' ', '+')}&cat=All"
            print(f"🔍 Searching: {search_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=self.headers, timeout=30) as response:
                    if response.status != 200:
                        print(f"❌ HTTP Error: {response.status}")
                        return []
                    
                    content = await response.text()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    movies = []
                    
                    # IMPROVED PARSING: Find all movie links
                    all_links = soup.find_all('a', href=True)
                    
                    for link in all_links:
                        href = link.get('href', '')
                        text = link.get_text().strip()
                        
                        # Filter movie links more accurately
                        if ('/movie/' in href or query.lower() in text.lower()) and len(text) > 10:
                            # Construct full URL
                            if href.startswith('/'):
                                full_url = self.base_url + href
                            else:
                                full_url = href
                            
                            # Skip if not a valid movie page
                            if not full_url.endswith('.html'):
                                continue
                            
                            # Clean title
                            title = text
                            
                            movies.append({
                                'title': title,
                                'url': full_url,
                                'poster': None
                            })
                            print(f"✅ Found: {title}")
                    
                    # Remove duplicates
                    unique_movies = []
                    seen_urls = set()
                    for movie in movies:
                        if movie['url'] not in seen_urls:
                            seen_urls.add(movie['url'])
                            unique_movies.append(movie)
                    
                    print(f"🎯 Total unique movies found: {len(unique_movies)}")
                    return unique_movies[:6]
                    
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []
    
    async def get_movie_details(self, movie_url):
        """Get movie details with IMPROVED link extraction"""
        try:
            print(f"🔗 Getting details: {movie_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(movie_url, headers=self.headers, timeout=30) as response:
                    if response.status != 200:
                        return {'title': 'Unknown', 'poster': None, 'download_links': {}}
                    
                    content = await response.text()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Extract title
                    title = "Unknown Movie"
                    title_elem = soup.find('title')
                    if title_elem:
                        title = title_elem.text.strip().replace(' - SkymoviesHD', '').replace('Full Movie Download', '').strip()
                    
                    # IMPROVED: Extract download links
                    download_links = await self.extract_download_links_improved(soup, movie_url)
                    
                    print(f"✅ Found {sum(len(links) for links in download_links.values())} download links")
                    return {
                        'title': title,
                        'poster': None,
                        'download_links': download_links,
                        'url': movie_url
                    }
                    
        except Exception as e:
            print(f"❌ Details error: {e}")
            return {'title': 'Unknown', 'poster': None, 'download_links': {}}
    
    async def extract_download_links_improved(self, soup, movie_url):
        """IMPROVED: Extract download links with multiple methods"""
        all_links = []
        
        # METHOD 1: Find download section (Bolly class)
        download_section = soup.find('div', class_='Bolly')
        if download_section:
            print("✅ Found download section (Bolly)")
            links = download_section.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text = link.get_text().strip()
                
                if href.startswith('http'):
                    all_links.append({
                        'url': href,
                        'text': text,
                        'source': 'download_section'
                    })
        
        # METHOD 2: Find all links with download keywords
        download_keywords = ['download', 'server', 'watch online', 'get link', 'link']
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            text = a_tag.get_text().strip().lower()
            
            if href.startswith('http') and any(keyword in text for keyword in download_keywords):
                all_links.append({
                    'url': href,
                    'text': text,
                    'source': 'keyword_match'
                })
        
        # METHOD 3: Find links near download-related text
        download_texts = soup.find_all(string=re.compile(r'download|server|watch online', re.IGNORECASE))
        for text in download_texts:
            parent = text.parent
            if parent:
                links = parent.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    if href.startswith('http'):
                        all_links.append({
                            'url': href,
                            'text': link.get_text().strip(),
                            'source': 'text_proximity'
                        })
        
        print(f"🔍 Found {len(all_links)} potential download links")
        
        # Categorize links
        categorized_links = {category: [] for category in self.cloud_hosts.keys()}
        categorized_links['watch_online'] = []
        categorized_links['other'] = []
        
        for link in all_links:
            url = link['url']
            text = link['text'].lower()
            
            # Watch Online links
            if 'watch online' in text or 'watch' in text:
                categorized_links['watch_online'].append(url)
                print(f"🎥 Watch Online: {url}")
                continue
            
            # Categorize by cloud provider
            link_categorized = False
            for category, hosts in self.cloud_hosts.items():
                for host in hosts:
                    if host in url.lower():
                        categorized_links[category].append(url)
                        print(f"☁️ {category}: {url}")
                        link_categorized = True
                        break
                if link_categorized:
                    break
            
            # If not categorized, add to other
            if not link_categorized:
                categorized_links['other'].append(url)
                print(f"🌐 Other: {url}")
        
        return categorized_links
    
    async def extract_download_links(self, soup):
        """Legacy function for compatibility"""
        return await self.extract_download_links_improved(soup, "")
