import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import hashlib

class SkyMoviesScraper:
    def __init__(self):
        self.base_url = "https://skymovieshd.mba"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://skymovieshd.mba/'
        }
        
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=30)
        
        # Cloud hosts for categorization
        self.cloud_hosts = {
            'gofile': ['gofile.io', 'gofile.'],
            'streamtape': ['streamtape.to', 'streamtape.com'],
            'hubdrive': ['hubdrive.', 'hubdrive.space'],
            'hubcloud': ['hubcloud.fit'],
            'filepress': ['filepress.', 'filepress.today'],
            'vikingfile': ['vikingfile.com'],
            'gdflix': ['gdflix.dev', 'gdflix.'],
            'gdtot': ['gdtot.', 'gdtot.lol', 'gdtot.sbs', 'gdtot.cc', 'gdtot.dad'],
            'uptomega': ['uptomega.net'],
            'indishare': ['indishare.info'],
            'uploadhub': ['uploadhub.'],
            'filepv': ['filepv.com'],
            'clicknupload': ['clicknupload.'],
            '1cloudfile': ['1cloudfile.com'],
            'vinovo': ['vinovo.'],
            'megaup': ['megaup.net'],
            'ddownload': ['ddownload.com'],
            'desiupload': ['desiupload.'],
            'uploadflix': ['uploadflix.com'],
            'hglink': ['hglink.'],
            'frdl': ['frdl.io'],
            'dsvplay': ['dsvplay.com'],
            'dropdownload': ['drop.download'],
            'datavaults': ['datavaults.co'],
            'voe': ['voe.sx'],
            '1fichier': ['1fichier.com'],
            'mixloads': ['mixloads.to']
        }
        
        # Links with this text will be SCRAPED (not become buttons)
        self.server_regex = re.compile(r'server \d+', re.IGNORECASE)

    async def get_session(self):
        """Get or create session with connection pooling"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            self.session = aiohttp.ClientSession(connector=connector, timeout=self.timeout, headers=self.headers)
        return self.session

    async def close_session(self):
        """Close session properly"""
        if self.session and not self.session.closed:
            await self.session.close()

    def normalize_url(self, url):
        """Normalize URL to remove duplicates"""
        parsed = urlparse(url)
        query_params = []
        for param in parsed.query.split('&'):
            if not any(track in param.lower() for track in ['utm_', 'ref=', 'source=', 'campaign=', 'views:', 'view=']):
                query_params.append(param)
        clean_query = '&'.join(query_params)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean_query:
            normalized += f"?{clean_query}"
        return normalized.rstrip('/')

    def get_url_fingerprint(self, url):
        """Create fingerprint for URL to detect duplicates"""
        normalized = self.normalize_url(url)
        
        if 'gofile.io/d/' in normalized:
            match = re.search(r'gofile.io/d/([a-zAZ0-9]+)', normalized)
            if match: return f"gofile_{match.group(1)}"
        elif 'streamtape.to/v/' in normalized:
            match = re.search(r'streamtape.to/v/([a-zA-Z0-9]+)', normalized)
            if match: return f"streamtape_{match.group(1)}"
        elif 'vikingfile.com/f/' in normalized:
            match = re.search(r'vikingfile.com/f/([a-zA-Z0-9]+)', normalized)
            if match: return f"vikingfile_{match.group(1)}"
        elif 'hubdrive.' in normalized:
            match = re.search(r'hubdrive.[^/]+/file/([0-9]+)', normalized)
            if match: return f"hubdrive_{match.group(1)}"
        elif 'hubcloud.fit/drive/' in normalized:
            match = re.search(r'hubcloud.fit/drive/([a-zA-Z0-9]+)', normalized)
            if match: return f"hubcloud_{match.group(1)}"
        elif 'gdflix.dev/file/' in normalized:
            match = re.search(r'gdflix.dev/file/([a-zA-Z0-9]+)', normalized)
            if match: return f"gdflix_{match.group(1)}"
        elif 'filepress.today/file/' in normalized:
            match = re.search(r'filepress.today/file/([a-f0-9]+)', normalized)
            if match: return f"filepress_{match.group(1)}"
        elif 'gdtot.' in normalized:
            match = re.search(r'gdtot\.[^/]+/file/([0-9]+)', normalized)
            if match: return f"gdtot_{match.group(1)}"
        
        return hashlib.md5(normalized.encode()).hexdigest()

    async def make_request(self, url, max_retries=3):
        """Make HTTP request with retry logic"""
        session = await self.get_session()
        for attempt in range(max_retries):
            try:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status in [429, 500, 502, 503]:
                        wait_time = 2 ** attempt
                        print(f"⚠️ Retry {attempt + 1} for {url} after {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == max_retries - 1:
                    print(f"❌ Request failed after {max_retries} attempts: {e}")
                    # Do not raise, return None
                    return None
                wait_time = 2 ** attempt
                print(f"⚠️ Connection error, retry {attempt + 1} after {wait_time}s")
                await asyncio.sleep(wait_time)
        return None

    async def get_all_search_results(self, query):
        """Get all search results for pagination calculation"""
        try:
            search_url = f"{self.base_url}/search.php?search={query.replace(' ', '+')}&cat=All"
            print(f"🔍 Getting all results: {query}")
            
            content = await self.make_request(search_url)
            if not content:
                return []
                
            soup = BeautifulSoup(content, 'html.parser')
            movies = []
            
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text().strip()
                
                if ('.html' in href and len(text) > 5 and 'category' not in href):
                    if href.startswith('/'):
                        full_url = self.base_url + href
                    else:
                        full_url = href
                    
                    if not full_url.startswith(self.base_url):
                        continue
                    
                    title = text
                    movies.append({
                        'title': title,
                        'url': full_url,
                        'poster': None
                    })
            
            unique_movies = []
            seen_urls = set()
            for movie in movies:
                if movie['url'] not in seen_urls:
                    seen_urls.add(movie['url'])
                    unique_movies.append(movie)
            
            return unique_movies
            
        except Exception as e:
            print(f"❌ Get all results error: {e}")
            return []

    async def _extract_direct_links_from_howblogs(self, howblogs_url):
        """[Internal] Extract direct links from howblogs.xyz pages"""
        try:
            print(f"🔗 Extracting from howblogs: {howblogs_url}")
            
            content = await self.make_request(howblogs_url)
            if not content:
                return []
                
            soup = BeautifulSoup(content, 'html.parser')
            all_urls = []
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '')
                if href.startswith('http'):
                    all_urls.append(href)
            
            text_content = soup.get_text()
            
            # --- THIS IS THE FIXED REGEX ---
            url_pattern = r'https?://[^\s<>"{}|\\^]+'
            # The old, broken one was: r'https(://[^\s<>"{}|\\^]+'
            
            text_urls = re.findall(url_pattern, text_content)
            all_urls.extend(text_urls)
            
            download_domains = [host for hosts in self.cloud_hosts.values() for host in hosts]
            
            unique_links = {}
            for url in all_urls:
                fingerprint = self.get_url_fingerprint(url)
                if fingerprint not in unique_links:
                    unique_links[fingerprint] = url
            
            direct_links = []
            for url in unique_links.values():
                if any(domain in url.lower() for domain in download_domains):
                    direct_links.append(url)
            
            print(f"✅ Extracted {len(direct_links)} unique direct links from howblogs")
            return direct_links
            
        except Exception as e:
            print(f"❌ Howblogs extraction error: {e}")
            return []

    async def follow_redirects_final(self, url):
        """Follow redirects to get final URL with timeout"""
        try:
            session = await self.get_session()
            async with session.get(url, allow_redirects=True, timeout=10) as response:
                return str(response.url)
        except Exception as e:
            print(f"❌ Redirect error for {url}: {e}")
            return url

    def _extract_poster(self, soup):
        """Extract movie poster URL"""
        try:
            poster_img = soup.find('img', class_='img-responsive')
            if poster_img:
                src = poster_img.get('src')
                if src and src.startswith('http'):
                    return src
            
            poster_img = soup.select_one('div.poster img')
            if poster_img:
                src = poster_img.get('src')
                if src and src.startswith('http'):
                    return src

            for img in soup.find_all('img'):
                if 'poster' in img.get('src', '').lower() or 'thumbnail' in img.get('src', '').lower():
                     src = img.get('src')
                     if src and src.startswith('http'):
                        return src

        except Exception as e:
            print(f"ℹ️ Poster extraction warning: {e}")
        return None

    async def extract_and_categorize_howblogs(self, howblogs_url):
        """Public helper to extract and categorize links from a howblogs URL"""
        try:
            direct_links = await self._extract_direct_links_from_howblogs(howblogs_url)
            
            categorized_links = {category: [] for category in self.cloud_hosts.keys()}
            categorized_links['other'] = []
            
            for url in direct_links:
                link_categorized = False
                for category, hosts in self.cloud_hosts.items():
                    for host in hosts:
                        if host in url.lower():
                            categorized_links[category].append(url)
                            link_categorized = True
                            break
                    if link_categorized:
                        break
                if not link_categorized:
                    categorized_links['other'].append(url)
            
            return categorized_links
            
        except Exception as e:
            print(f"❌ Special quality extraction error: {e}")
            return {}

    async def _extract_download_links(self, soup, movie_url):
        """
        Scrapes all links and divides them into two groups:
        1. `links_to_scrape`: "Server" links that contain direct links.
        2. `button_links`: All other links that become dynamic buttons.
        """
        
        links_to_scrape = []  # URLs to scrape (e.g., Server 1, Server 2)
        button_links = {}     # {text: url} for dynamic buttons
        final_direct_links = {} # {fingerprint: url} for uncategorized direct links
        processed_links = set() # Track processed hrefs
        
        all_a_tags = soup.find_all('a', href=True)
        
        for link in all_a_tags:
            href = link.get('href', '')
            text = link.get_text().strip()
            
            if not text or not href.startswith('http') and not href.startswith('/'):
                continue
            
            if href.startswith('/'):
                href = urljoin(self.base_url, href)

            if href in processed_links:
                continue
            processed_links.add(href)

            server_match = self.server_regex.search(text)
            
            if server_match:
                print(f"ℹ️ Queued for scraping: {text} -> {href}")
                links_to_scrape.append(href)
            
            elif 'howblogs.xyz' in href or 'watchadsontape.com' in href or 'drive' in text.lower() or 'p Links' in text or 'HEVC' in text or 'WATCH ONLINE' in text:
                if text not in button_links:
                    print(f"✅ Found Button: {text} -> {href}")
                    button_links[text] = href
            
            else:
                final_url = await self.follow_redirects_final(href)
                if final_url:
                    fingerprint = self.get_url_fingerprint(final_url)
                    if fingerprint not in final_direct_links and any(
                        host in final_url.lower() for hosts in self.cloud_hosts.values() for host in hosts
                    ):
                        final_direct_links[fingerprint] = final_url
                        print(f"✅ Found direct link: {final_url}")

        print(f"🔄 Scraping {len(links_to_scrape)} 'Server' links...")
        for url in links_to_scrape:
            direct_links = await self._extract_direct_links_from_howblogs(url)
            for direct_link in direct_links:
                fingerprint = self.get_url_fingerprint(direct_link)
                if fingerprint not in final_direct_links:
                    final_direct_links[fingerprint] = direct_link
                    
        categorized_links = {category: [] for category in self.cloud_hosts.keys()}
        categorized_links['other'] = []
        
        for url in final_direct_links.values():
            link_categorized = False
            for category, hosts in self.cloud_hosts.items():
                for host in hosts:
                    if host in url.lower():
                        categorized_links[category].append(url)
                        link_categorized = True
                        break
                if link_categorized:
                    break
            if not link_categorized:
                categorized_links['other'].append(url)

        return {
            'main_links': categorized_links,
            'button_links': button_links
        }


    async def get_movie_details(self, movie_url):
        """Get movie details with improved error handling"""
        try:
            print(f"🔗 Getting details: {movie_url}")
            
            content = await self.make_request(movie_url)
            if not content:
                # Return a valid structure even on failure
                return {'title': 'Unknown', 'poster': None, 'main_links': {}, 'button_links': {}, 'url': movie_url}
            
            soup = BeautifulSoup(content, 'html.parser')
            
            title = "Unknown Movie"
            title_elem = soup.find('title')
            if title_elem:
                title = title_elem.text.strip()
                title = re.sub(r' - SkymoviesHD.*|Full Movie Download.*', '', title).strip()
            
            poster_url = self._extract_poster(soup)
            
            links_data = await self._extract_download_links(soup, movie_url)
            
            total_links = sum(len(links) for links in links_data['main_links'].values())
            print(f"✅ Found {total_links} direct links (Gofile, Other, etc.)")
            print(f"✅ Found {len(links_data['button_links'])} dynamic button links (Watch, Quality, etc.)")
            
            return {
                'title': title,
                'poster': poster_url,
                'main_links': links_data['main_links'],
                'button_links': links_data['button_links'],
                'url': movie_url # Make sure 'url' is always present
            }
            
        except Exception as e:
            print(f"❌ Details error for {movie_url}: {e}")
            # --- THIS IS THE SECOND FIX ---
            # Return a valid structure on error, including the URL
            return {'title': 'Unknown', 'poster': None, 'main_links': {}, 'button_links': {}, 'url': movie_url}

