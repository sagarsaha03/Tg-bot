import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import hashlib

class KatMovieFixScraper:
    def __init__(self):
        self.base_url = "https://katmoviefix.casa"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://katmoviefix.casa/'
        }
        
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def get_session(self):
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            self.session = aiohttp.ClientSession(connector=connector, timeout=self.timeout, headers=self.headers)
        return self.session

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def make_request(self, url, max_retries=3):
        session = await self.get_session()
        for attempt in range(max_retries):
            try:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status in [429, 500, 502, 503]:
                        wait_time = 2 ** attempt
                        print(f"⚠️ [KatMovieFix] Retry {attempt + 1} for {url} after {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ [KatMovieFix] HTTP {response.status} for {url}")
                        break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == max_retries - 1:
                    print(f"❌ [KatMovieFix] Request failed: {e}")
                    return None
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
        return None

    async def get_all_search_results(self, query):
        try:
            search_url = f"{self.base_url}/?s={query.replace(' ', '+')}"
            print(f"🔍 [KatMovieFix] Searching: {query} -> {search_url}")
            
            content = await self.make_request(search_url)
            if not content:
                print(f"❌ [KatMovieFix] No content received for {query}")
                return []
                
            soup = BeautifulSoup(content, 'html.parser')
            movies = []
            
            # Debug: Print page title to see if we're getting the right page
            title = soup.find('title')
            if title:
                print(f"📄 [KatMovieFix] Page title: {title.text}")
            
            # Method 1: Look for articles (WordPress style)
            articles = soup.find_all('article')
            print(f"📝 [KatMovieFix] Found {len(articles)} articles")
            
            for article in articles:
                link = article.find('a', href=True)
                if link:
                    href = link.get('href', '')
                    text = link.get_text().strip()
                    
                    if href and text and len(text) > 10:
                        if not href.startswith('http'):
                            href = urljoin(self.base_url, href)
                        
                        # Get poster image
                        poster = None
                        img = article.find('img')
                        if img and img.get('src'):
                            poster = img.get('src')
                            if not poster.startswith('http'):
                                poster = urljoin(self.base_url, poster)
                        
                        movies.append({
                            'title': text,
                            'url': href,
                            'poster': poster
                        })
                        print(f"✅ [KatMovieFix] Found: {text} -> {href}")
            
            # Method 2: Look for any movie links in the page
            if not movies:
                print("🔄 [KatMovieFix] Trying alternative method...")
                all_links = soup.find_all('a', href=True)
                movie_links = []
                
                for link in all_links:
                    href = link.get('href', '')
                    text = link.get_text().strip()
                    
                    # Look for movie pages (contain .html or /movie/ or have movie-like titles)
                    if (href.endswith('.html') or '/movie/' in href or '/series/' in href) and len(text) > 10:
                        if not href.startswith('http'):
                            href = urljoin(self.base_url, href)
                        
                        if self.base_url in href or 'katmoviefix' in href:
                            movie_links.append({
                                'title': text,
                                'url': href,
                                'poster': None
                            })
                            print(f"✅ [KatMovieFix] Alternative found: {text}")
                
                movies.extend(movie_links)
            
            # Method 3: Look for h2/h3 headings with links
            if not movies:
                print("🔄 [KatMovieFix] Trying heading method...")
                headings = soup.find_all(['h2', 'h3'])
                for heading in headings:
                    link = heading.find('a', href=True)
                    if link:
                        href = link.get('href', '')
                        text = link.get_text().strip()
                        
                        if href and text and len(text) > 10:
                            if not href.startswith('http'):
                                href = urljoin(self.base_url, href)
                            
                            movies.append({
                                'title': text,
                                'url': href,
                                'poster': None
                            })
                            print(f"✅ [KatMovieFix] Heading found: {text}")
            
            # Remove duplicates
            unique_movies = []
            seen_urls = set()
            for movie in movies:
                if movie['url'] not in seen_urls:
                    seen_urls.add(movie['url'])
                    unique_movies.append(movie)
            
            print(f"✅ [KatMovieFix] Total unique results: {len(unique_movies)}")
            return unique_movies
            
        except Exception as e:
            print(f"❌ [KatMovieFix] Search error: {e}")
            return []

    async def get_movie_details(self, movie_url):
        try:
            print(f"🔗 [KatMovieFix] Getting details: {movie_url}")
            
            content = await self.make_request(movie_url)
            if not content:
                return {'title': 'Unknown', 'poster': None, 'main_links': {}, 'button_links': {}, 'url': movie_url}
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract title
            title = "Unknown Movie"
            title_elem = soup.find('title') or soup.find('h1') or soup.find('h2')
            if title_elem:
                title = title_elem.text.strip()
                title = re.sub(r' - KatMovieFix.*|Download.*|Watch Online.*', '', title).strip()
            
            # Extract poster
            poster = None
            img = soup.find('img', class_='wp-post-image') or soup.find('img', src=re.compile(r'poster|thumb'))
            if img and img.get('src'):
                poster = img.get('src')
                if not poster.startswith('http'):
                    poster = urljoin(self.base_url, poster)
            
            # Extract all links from the page
            all_links = []
            
            # From anchor tags
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('http'):
                    all_links.append(href)
            
            # From text content
            text_content = soup.get_text()
            url_pattern = r'https?://[^\s<>"{}|\\^]+'
            text_urls = re.findall(url_pattern, text_content)
            all_links.extend(text_urls)
            
            # Categorize links
            main_links = {}
            button_links = {}
            
            for url in all_links:
                # Pack links (KatLinks)
                if 'katlinks.in/archives/' in url:
                    button_links['📦 Pack Links'] = url
                
                # Download links (GDflix)
                elif 'new7.gdflix.net/file/' in url:
                    if 'gdflix' not in main_links:
                        main_links['gdflix'] = []
                    main_links['gdflix'].append(url)
                
                # Stream links (Dumbalag)
                elif 'dumbalag.com/' in url:
                    button_links['🎬 Stream Online'] = url
                
                # Other file hosts
                elif any(host in url for host in ['gofile.io', 'filepress.', 'uptomega.net', 'streamtape.com']):
                    domain = urlparse(url).netloc.replace('www.', '')
                    if domain not in main_links:
                        main_links[domain] = []
                    main_links[domain].append(url)
            
            # Also get button links from anchor text
            for link in soup.find_all('a', href=True):
                text = link.get_text().strip()
                href = link.get('href', '')
                
                if href.startswith('http'):
                    if any(keyword in text.lower() for keyword in ['download', 'watch', 'stream', 'online', '720p', '1080p', '480p', 'episode']):
                        if text not in button_links:
                            button_links[text] = href

            print(f"✅ [KatMovieFix] Found {len(main_links)} main links, {len(button_links)} button links")
            
            return {
                'title': title,
                'poster': poster, 
                'main_links': main_links,
                'button_links': button_links,
                'url': movie_url
            }
            
        except Exception as e:
            print(f"❌ [KatMovieFix] Details error: {e}")
            return {'title': 'Unknown', 'poster': None, 'main_links': {}, 'button_links': {}, 'url': movie_url}
