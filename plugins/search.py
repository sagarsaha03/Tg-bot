import asyncio
from time import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified
from scraper.skymovies import SkyMoviesScraper
import re
import math

# --- Bot Configuration ---

# !! IMPORTANT: Add your numeric Telegram user ID here
ADMIN_IDS = {6687248633} 

# --- Global State ---
user_searches = {}
PM_ENABLED = True

def shorten_url_display(url):
    """Shorten URL for better display"""
    if len(url) > 60:
        if 'gofile.io/d/' in url:
            match = re.search(r'gofile.io/d/([a-zA-Z0-9]+)', url)
            if match: return f"https://gofile.io/d/{match.group(1)}"
        elif 'streamtape.to/v/' in url:
            match = re.search(r'streamtape.to/v/([a-zA-Z0-9]+)', url)
            if match: return f"https://streamtape.to/v/{match.group(1)}"
        elif 'vikingfile.com/f/' in url:
            match = re.search(r'vikingfile.com/f/([a-zA-Z0-9]+)', url)
            if match: return f"https://vikingfile.com/f/{match.group(1)}"
        elif 'hubdrive.' in url:
            match = re.search(r'hubdrive.[^/]+/file/([0-9]+)', url)
            if match: return f"https://hubdrive.space/file/{match.group(1)}"
        elif 'hubcloud.fit/drive/' in url:
            match = re.search(r'hubcloud.fit/drive/([a-zA-Z0-9]+)', url)
            if match: return f"https:://hubcloud.fit/drive/{match.group(1)}"
        elif 'gdflix.' in url:
            match = re.search(r'gdflix.[^/]+/file/([a-zA-Z0-9]+)', url)
            if match: return f"https://gdflix.dev/file/{match.group(1)}"
        elif 'filepress.' in url:
            match = re.search(r'filepress.[^/]+/file/([a-f0-9]+)', url)
            if match: return f"https://filepress.today/file/{match.group(1)}"
        elif 'gdtot.' in url:
            match = re.search(r'gdtot\.[^/]+/file/([0-9]+)', url)
            if match: return f"https://gdtot.lol/file/{match.group(1)}"
    return url

def create_scraped_links_message(movie_title, download_links, button_text=""):
    """Create formatted message for links scraped from a button (e.g., a howblogs page)"""
    message_text = f"📌 {movie_title}\n"
    
    if button_text:
        message_text += f"🌐 {button_text} 📥\n\n"
    
    # Define display order
    display_order = [
        ('gofile', '🔰 GoFile Links'),
        ('streamtape', '🐬 StreamTape Links'), 
        ('hubdrive', '🛡️ HubDrive Links'),
        ('hubcloud', '☁️ HubCloud Links'),
        ('gdflix', '📦 GDFlix Links'),
        ('gdtot', '📂 GDTot Links'),
        ('filepress', '🗂️ FilePress Links'),
        ('vikingfile', '⚡ VikingFile Links'),
        ('uptomega', '☁️ Uptomega Links'),
        ('indishare', '📎 IndiShare Links'),
    ]
    
    links_found = False
    total_links = 0
    
    # Get all categories that have links, in the correct order
    categories_with_links = []
    
    # Add ordered categories first
    for key, name in display_order:
        if download_links.get(key):
            categories_with_links.append((key, name))
            
    # Add 'other' category last
    if download_links.get('other'):
        categories_with_links.append(('other', '🔗 Other Drive Links'))
        
    # Add any other categories that weren't in the list
    ordered_keys = [k[0] for k in categories_with_links]
    for key, links in download_links.items():
        if key not in ordered_keys and links:
            categories_with_links.append((key, f"🔗 {key.title()} Links"))

    for category_key, display_name in categories_with_links:
        links = download_links.get(category_key, [])
        if links:
            message_text += f"**{display_name}**\n"
            shown_links = set()
            for link in links: # Show all links
                display_link = shorten_url_display(link)
                if display_link not in shown_links:
                    shown_links.add(display_link)
                    message_text += f"• {display_link}\n"
            message_text += "\n"
            links_found = True
            total_links += len(links)
    
    if not links_found:
        message_text += "❌ No direct download links found on this page.\n\n"
    
    if total_links > 0:
        message_text += f"📊 Total Links Found: {total_links}\n\n"
        
    message_text += "Powered By @Sseries_Area"
    return message_text, total_links

def build_main_links_message(user_data):
    """--- NEW PAGINATION LOGIC ---
    Builds the main links message (caption) and dynamic buttons.
    Paginates the *categories* of links, 4 at a time.
    """
    
    movie_title = user_data.get('current_movie_title', 'Unknown Movie')
    download_links = user_data.get('main_links', {})
    button_links = user_data.get('button_links', {})
    
    # Store button links in user_data for callback handler
    user_data['button_links_list'] = list(button_links.items())

    # --- 1. Category Pagination Logic ---
    
    # Define full display order
    display_order = [
        ('gofile', '🔰 GoFile Links'),
        ('streamtape', '🐬 StreamTape Links'), 
        ('hubdrive', '🛡️ HubDrive Links'),
        ('hubcloud', '☁️ HubCloud Links'),
        ('gdflix', '📦 GDFlix Links'),
        ('gdtot', '📂 GDTot Links'),
        ('filepress', '🗂️ FilePress Links'),
        ('vikingfile', '⚡ VikingFile Links'),
        ('uptomega', '☁️ Uptomega Links'),
        ('indishare', '📎 IndiShare Links'),
    ]
    
    # Get all categories *that have links*
    available_categories = []
    
    # Add ordered categories first
    for key, name in display_order:
        if download_links.get(key):
            available_categories.append((key, name))
            
    # Add 'other' category
    if download_links.get('other'):
        available_categories.append(('other', '🔗 Other Drive Links'))
        
    # Add any other stragglers
    ordered_keys = [k[0] for k in available_categories]
    for key, links in download_links.items():
        if key not in ordered_keys and links:
            available_categories.append((key, f"🔗 {key.title()} Links"))

    # Now, paginate this 'available_categories' list
    category_page = user_data.get('category_page', 1)
    categories_per_page = 4 # As per user's example
    
    total_categories = len(available_categories)
    total_category_pages = math.ceil(total_categories / categories_per_page)
    
    start_index = (category_page - 1) * categories_per_page
    end_index = start_index + categories_per_page
    current_categories_chunk = available_categories[start_index:end_index]
    
    user_data['total_category_pages'] = total_category_pages # Store for the button

    # --- 2. Build Message Caption ---
    caption_text = f"📌 **{movie_title}**\n\n"
    links_found_on_this_page = False
    
    for category_key, display_name in current_categories_chunk:
        links = download_links.get(category_key, [])
        if links:
            caption_text += f"**{display_name}**\n"
            links_found_on_this_page = True
            shown_links = set()
            for link in links: # Show all links for these categories
                display_link = shorten_url_display(link)
                if display_link not in shown_links:
                    shown_links.add(display_link)
                    caption_text += f"• {display_link}\n"
            caption_text += "\n"

    if not links_found_on_this_page:
        if category_page == 1 and total_categories == 0:
             caption_text += "❌ No direct download links (from Servers) were found.\n\n"
        else:
             caption_text += "• No more links on this page.\n\n"

    caption_text += "Powered By @Sseries_Area"
    
    # --- 3. Build Dynamic Buttons ---
    buttons = []
    
    button_links_list = user_data.get('button_links_list', [])
    for i, (text, url) in enumerate(button_links_list):
        text_lower = text.lower()
        emoji = "🎬" # Default
        
        if "watch online" in text_lower:
            emoji = "👀"
        elif "drive" in text_lower:
            emoji = "📦"
        
        buttons.append([
            InlineKeyboardButton(f"{emoji} {text}", callback_data=f"btn_link_{i}")
        ])

    # --- 4. Build Category pagination button ---
    category_buttons = []
    if total_category_pages > 1:
        next_page = category_page + 1
        if next_page > total_category_pages:
            next_page = 1 # Loop back to 1
        
        category_buttons.append(
            InlineKeyboardButton(
                f"🔄 Refresh Links {category_page}/{total_category_pages}", 
                callback_data=f"category_page_{next_page}"
            )
        )
    if category_buttons:
        buttons.append(category_buttons)

    # --- 5. Navigation buttons ---
    buttons.extend([
        [InlineKeyboardButton("🔙 Back to Results", callback_data="back_results")],
        [InlineKeyboardButton("🔄 Search Again", callback_data="new_search")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    return caption_text, InlineKeyboardMarkup(buttons)

# --- Admin Commands ---

@Client.on_message(filters.command("pm_on") & filters.user(*ADMIN_IDS))
async def pm_on(bot, message):
    global PM_ENABLED
    PM_ENABLED = True
    await message.reply_text("✅ Private message searching is now **ENABLED**.")

@Client.on_message(filters.command("pm_off") & filters.user(*ADMIN_IDS))
async def pm_off(bot, message):
    global PM_ENABLED
    PM_ENABLED = False
    await message.reply_text("❌ Private message searching is now **DISABLED**.")

# --- Bot Handlers ---

@Client.on_message(filters.text & (filters.group | filters.private) & filters.incoming)
async def simple_search(bot, message):
    """Simple search without database dependencies"""
    if message.text.startswith("/"):
        return
        
    if message.chat.type == 'private' and not PM_ENABLED:
        await message.reply_text("❌ Searching in PM is currently disabled by the admin.")
        return
        
    query = message.text.strip()
    
    if len(query) < 3:
        await message.reply_text("❌ Please enter at least 3 characters for search.")
        return
        
    try:
        search_msg = await message.reply_text("🔍 Searching movies...")
        
        scraper = SkyMoviesScraper()
        all_movies = await scraper.get_all_search_results(query)
        await scraper.close_session()
        
        if not all_movies:
            await search_msg.edit_text("❌ No movies found. Try different keywords.")
            return
        
        results_per_page = 4
        total_results = len(all_movies)
        total_pages = (total_results + results_per_page - 1) // results_per_page
        
        current_page = 1
        start_index = (current_page - 1) * results_per_page
        end_index = start_index + results_per_page
        current_movies = all_movies[start_index:end_index]
        
        user_searches[message.from_user.id] = {
            'all_movies': all_movies,
            'current_movies': current_movies,
            'timestamp': time(),
            'query': query,
            'current_page': current_page,
            'total_pages': total_pages,
            'total_results': total_results
        }
        
        start_num = start_index + 1
        
        results_text = f"🔍 Search Results for '{query}' (Page {current_page}):\n\n"
        for i, movie in enumerate(current_movies, start_num):
            results_text += f"{i}. {movie['title']}\n\n"
        
        results_text += f"📄 Page {current_page}/{total_pages} | Total Results: {total_results}\n\n"
        results_text += "Powered By @Sseries_Area"
        
        buttons = []
        row = []
        for i, movie in enumerate(current_movies, start_num):
            row.append(InlineKeyboardButton(f"🎬 {i}", callback_data=f"mov_{i}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        pagination_row = []
        if total_pages > 1:
            pagination_row.append(InlineKeyboardButton("➡️ Next Page", callback_data="next_page"))
        buttons.append(pagination_row)
        
        buttons.append([InlineKeyboardButton("🔄 Refresh Search", callback_data="refresh")])
        
        await search_msg.edit_text(
            text=results_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        print(f"❌ Search error: {e}")
        await message.reply_text("❌ Search temporarily unavailable.")

@Client.on_callback_query(filters.regex(r"^mov_"))
async def show_download_links(bot, update):
    """Show download links (with poster) for selected movie"""
    try:
        user_id = update.from_user.id
        movie_global_index = int(update.data.split("_", 1)[1])
        
        user_data = user_searches.get(user_id)
        if not user_data or time() - user_data['timestamp'] > 600:
            await update.answer("❌ Search expired. Please search again.", show_alert=True)
            return

        all_movies = user_data['all_movies']
        
        if movie_global_index > len(all_movies) or movie_global_index < 1:
            await update.answer("❌ Invalid selection", show_alert=True)
            return
            
        selected_movie = all_movies[movie_global_index - 1]
        movie_url = selected_movie['url']
        
        await update.answer("⏳ Loading download links...")
        
        try:
            await update.message.delete()
        except Exception:
            pass 
            
        processing_msg = await bot.send_message(
            chat_id=update.message.chat.id,
            text="🔄 Processing download links...\n\nThis may take 10-15 seconds."
        )
            
        scraper = SkyMoviesScraper()
        movie_details = None
        
        try:
            movie_details = await scraper.get_movie_details(movie_url)
        except Exception as e:
            print(f"❌ get_movie_details failed: {e}")
        
        await scraper.close_session() 
        
        if not movie_details or (not movie_details.get('main_links') and not movie_details.get('button_links')):
            await processing_msg.edit_text("❌ No download links found for this movie.")
            return
            
        user_data['current_movie_title'] = movie_details['title']
        user_data['current_movie_url'] = movie_details['url']
        user_data['poster'] = movie_details.get('poster')
        user_data['main_links'] = movie_details.get('main_links', {})
        user_data['button_links'] = movie_details.get('button_links', {})
        user_data['category_page'] = 1 # Reset to page 1
        
        caption, buttons = build_main_links_message(user_data)
        
        poster_url = user_data.get('poster')
        try:
            if poster_url:
                await bot.send_photo(
                    chat_id=update.message.chat.id,
                    photo=poster_url,
                    caption=caption,
                    reply_markup=buttons
                )
            else:
                await bot.send_message(
                    chat_id=update.message.chat.id,
                    text=caption,
                    reply_markup=buttons,
                    disable_web_page_preview=True
                )
            await processing_msg.delete() 
            
        except Exception as e:
            print(f"❌ Message send error: {e}")
            try:
                await processing_msg.edit_text(
                    text=caption,
                    reply_markup=buttons,
                    disable_web_page_preview=True
                )
            except Exception as e2:
                print(f"❌ Fallback message send error: {e2}")

    except Exception as e:
        print(f"❌ Download links error: {e}")
        try:
            await update.message.edit_text("❌ Error loading download links. Please try again.")
        except:
            pass

@Client.on_callback_query(filters.regex(r"^btn_link_"))
async def handle_dynamic_button_click(bot, update):
    """
    Handles clicks for ALL dynamic buttons (Watch Online, 480p, GDrive, etc.)
    Scrapes if it's a howblogs link, otherwise just displays the direct link.
    """
    try:
        user_id = update.from_user.id
        button_index = int(update.data.split('_')[-1])
        
        user_data = user_searches.get(user_id)
        if not user_data or not user_data.get('button_links_list'):
            await update.answer("❌ Search expired.", show_alert=True)
            return
        
        button_links_list = user_data.get('button_links_list', [])
        if button_index >= len(button_links_list):
            await update.answer("❌ Button link error.", show_alert=True)
            return

        button_text, special_url = button_links_list[button_index]
        movie_title = user_data.get('current_movie_title', 'Unknown Movie')
        
        await update.answer(f"⏳ Loading: {button_text}")
        
        processing_msg = await update.message.edit_text(
            f"🔄 Processing: {button_text}...",
            reply_markup=None 
        )
        
        if 'howblogs.xyz' in special_url:
            scraper = SkyMoviesScraper()
            scraped_links = await scraper.extract_and_categorize_howblogs(special_url)
            await scraper.close_session()
            
            if not scraped_links or sum(len(links) for links in scraped_links.values()) == 0:
                await processing_msg.edit_text(
                    f"❌ No links found for: {button_text}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]])
                )
                return
            
            message_text, total_links = create_scraped_links_message(
                movie_title,
                scraped_links,
                button_text
            )
        else:
            print(f"ℹ️ Displaying direct button link: {special_url}")
            message_text = f"📌 {movie_title}\n\n"
            message_text += f"🌐 {button_text} 📥\n\n"
            message_text += f"• {special_url}\n\n"
            message_text += "Powered By @Sseries_Area"
        
        buttons = [
            [InlineKeyboardButton("🔙 Back to Main Links", callback_data="back_to_main")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ]
        
        await processing_msg.edit_text(
            text=message_text,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
            
    except Exception as e:
        print(f"❌ Dynamic button click error: {e}")
        try:
            await update.message.edit_text("❌ Error loading links. Please try again.")
        except:
            pass

@Client.on_callback_query(filters.regex(r"^category_page_"))
async def paginate_category_links(bot, update):
    """Handle 'Refresh Links' for categories"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        if not user_data:
            await update.answer("❌ Search expired.", show_alert=True)
            return

        new_page = int(update.data.split('_')[-1])
        
        # Update the page in user_data
        user_data['category_page'] = new_page
        
        # Re-build the entire message
        caption, buttons = build_main_links_message(user_data)
        
        await update.message.edit_caption(
            caption=caption,
            reply_markup=buttons
        )
        
        total_pages = user_data.get('total_category_pages', 1)
        await update.answer(f"Page {new_page}/{total_pages} loaded")

    except MessageNotModified:
        await update.answer("ℹ️ No changes.")
    except Exception as e:
        print(f"❌ Category pagination error: {e}")
        await update.answer("❌ Error loading links.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^back_to_main$"))
async def back_to_main_links(bot, update):
    """Go back to main download links display"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        if not user_data:
            await update.answer("❌ No previous data found", show_alert=True)
            return
        
        user_data['category_page'] = 1 # Reset to page 1
        
        caption, buttons = build_main_links_message(user_data)
        
        await update.message.delete()
        
        poster_url = user_data.get('poster')
        if poster_url:
            await bot.send_photo(
                chat_id=update.message.chat.id,
                photo=poster_url,
                caption=caption,
                reply_markup=buttons
            )
        else:
            await bot.send_message(
                chat_id=update.message.chat.id,
                text=caption,
                reply_markup=buttons,
                disable_web_page_preview=True
            )
        
        await update.answer("↩️ Back to main links")
            
    except Exception as e:
        print(f"❌ Back to main links error: {e}")
        await update.answer("❌ Error going back", show_alert=True)

# --- Existing Pagination and Nav Handlers (No changes needed) ---

@Client.on_callback_query(filters.regex(r"^(next_page|prev_page)$"))
async def change_search_page(bot, update):
    """Show next/previous page of search results"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        if not user_data:
            await update.answer("❌ No previous search found", show_alert=True)
            return
            
        current_page = user_data.get('current_page', 1)
        total_pages = user_data.get('total_pages', 1)
        all_movies = user_data.get('all_movies', [])
        query = user_data.get('query', '')
        
        new_page = current_page
        if update.data == "next_page":
            if current_page >= total_pages:
                await update.answer("❌ Already on last page", show_alert=True)
                return
            new_page += 1
        elif update.data == "prev_page":
            if current_page <= 1:
                await update.answer("❌ Already on first page", show_alert=True)
                return
            new_page -= 1
            
        await update.answer(f"🔄 Loading page {new_page}...")
        
        results_per_page = 4
        start_index = (new_page - 1) * results_per_page
        end_index = start_index + results_per_page
        current_movies = all_movies[start_index:end_index]
        
        user_data['current_movies'] = current_movies
        user_data['current_page'] = new_page
        user_data['timestamp'] = time()
        
        start_num = start_index + 1
        
        results_text = f"🔍 Search Results for '{query}' (Page {new_page}):\n\n"
        for i, movie in enumerate(current_movies, start_num):
            results_text += f"{i}. {movie['title']}\n\n"
        
        results_text += f"📄 Page {new_page}/{total_pages} | Total Results: {len(all_movies)}\n\n"
        results_text += "Powered By @Sseries_Area"
        
        buttons = []
        row = []
        for i, movie in enumerate(current_movies, start_num):
            row.append(InlineKeyboardButton(f"🎬 {i}", callback_data=f"mov_{i}"))
            if len(row) == 2:
                buttons.append(row); row = []
        if row: buttons.append(row)
            
        pagination_row = []
        if new_page > 1:
            pagination_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="prev_page"))
        if new_page < total_pages:
            pagination_row.append(InlineKeyboardButton("➡️ Next", callback_data="next_page"))
        buttons.append(pagination_row)
        
        buttons.append([InlineKeyboardButton("🔄 Refresh Search", callback_data="refresh")])
        
        await update.message.edit_text(
            text=results_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"❌ Page change error: {e}")
        await update.answer("❌ Error loading page", show_alert=True)

@Client.on_callback_query(filters.regex(r"^back_results$"))
async def back_to_results(bot, update):
    """Go back to search results from links page"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        if not user_data:
            await update.answer("❌ No previous search found", show_alert=True)
            return
            
        current_movies = user_data['current_movies']
        query = user_data.get('query', 'your search')
        current_page = user_data.get('current_page', 1)
        total_pages = user_data.get('total_pages', 1)
        total_results = user_data.get('total_results', 0)
        
        results_per_page = 4
        start_index = (current_page - 1) * results_per_page
        start_num = start_index + 1
        
        results_text = f"🔍 Search Results for '{query}' (Page {current_page}):\n\n"
        for i, movie in enumerate(current_movies, start_num):
            results_text += f"{i}. {movie['title']}\n\n"
        
        results_text += f"📄 Page {current_page}/{total_pages} | Total Results: {total_results}\n\n"
        results_text += "Powered By @Sseries_Area"
        
        buttons = []
        row = []
        for i, movie in enumerate(current_movies, start_num):
            row.append(InlineKeyboardButton(f"🎬 {i}", callback_data=f"mov_{i}"))
            if len(row) == 2:
                buttons.append(row); row = []
        if row: buttons.append(row)
            
        pagination_row = []
        if current_page > 1:
            pagination_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="prev_page"))
        if current_page < total_pages:
            pagination_row.append(InlineKeyboardButton("➡️ Next", callback_data="next_page"))
        buttons.append(pagination_row)
        
        buttons.append([InlineKeyboardButton("🔄 Refresh Search", callback_data="refresh")])
        
        await update.message.delete()
        await bot.send_message(
            chat_id=update.message.chat.id,
            text=results_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await update.answer("↩️ Back to results")
            
    except Exception as e:
        print(f"❌ Back to results error: {e}")
        await update.answer("❌ Error going back", show_alert=True)

@Client.on_callback_query(filters.regex(r"^refresh$"))
async def refresh_search(bot, update):
    """Refresh the search results (re-run search)"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        query = ""
        if user_data:
            query = user_data.get('query', '')
            
        if not query:
            original_text = update.message.text
            if "Search Results for '" in original_text:
                try:
                    query = original_text.split("Search Results for '")[1].split("'")[0]
                except: pass
                    
        if not query:
            await update.answer("❌ Could not find search query", show_alert=True)
            return
            
        await update.answer("🔄 Refreshing search...")
        
        await update.message.edit_text("🔄 Refreshing search results...")
        
        scraper = SkyMoviesScraper()
        all_movies = await scraper.get_all_search_results(query)
        await scraper.close_session()
        
        if not all_movies:
            await update.message.edit_text("❌ No movies found after refresh.")
            return
        
        results_per_page = 4
        total_results = len(all_movies)
        total_pages = (total_results + results_per_page - 1) // results_per_page
        current_page = 1 
            
        start_index = (current_page - 1) * results_per_page
        end_index = start_index + results_per_page
        current_movies = all_movies[start_index:end_index]
        
        user_searches[user_id] = {
            'all_movies': all_movies,
            'current_movies': current_movies,
            'timestamp': time(),
            'query': query,
            'current_page': current_page,
            'total_pages': total_pages,
            'total_results': total_results
        }
        
        start_num = start_index + 1
        
        results_text = f"🔍 Search Results for '{query}' (Page {current_page} - Refreshed):\n\n"
        for i, movie in enumerate(current_movies, start_num):
            results_text += f"{i}. {movie['title']}\n\n"
        
        results_text += f"📄 Page {current_page}/{total_pages} | Total Results: {total_results}\n\n"
        results_text += "Powered By @Sseries_Area"
        
        buttons = []
        row = []
        for i, movie in enumerate(current_movies, start_num):
            row.append(InlineKeyboardButton(f"🎬 {i}", callback_data=f"mov_{i}"))
            if len(row) == 2:
                buttons.append(row); row = []
        if row: buttons.append(row)
            
        pagination_row = []
        if current_page < total_pages:
            pagination_row.append(InlineKeyboardButton("➡️ Next", callback_data="next_page"))
        buttons.append(pagination_row)
        
        buttons.append([InlineKeyboardButton("🔄 Refresh Again", callback_data="refresh")])
        
        await update.message.edit_text(
            text=results_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"❌ Refresh error: {e}")
        await update.answer("❌ Error refreshing search", show_alert=True)

@Client.on_callback_query(filters.regex(r"^new_search$"))
async def new_search_prompt(bot, update):
    """Prompt for new search"""
    try:
        await update.message.delete()
    except Exception:
        pass
        
    await bot.send_message(
        chat_id=update.message.chat.id,
        text="🔍 Enter your movie name to search:\n\nExample: Avengers Endgame\n\nPowered By @Sseries_Area"
    )
    await update.answer("🔍 Ready for new search")

@Client.on_callback_query(filters.regex(r"^close$"))
async def close_message(bot, update):
    """Close message"""
    try:
        await update.message.delete()
        user_id = update.from_user.id
        if user_id in user_searches:
            del user_searches[user_id]
    except Exception as e:
        print(f"❌ Close error: {e}")

# --- Start/Help/Stats Commands ---

@Client.on_message(filters.command("start"))
async def start_bot(bot, message):
    """Start command handler"""
    start_text = """
🤖 Movie Search Bot

🎬 **How to use:**
• Just type any movie name in this chat
• Select from search results  
• Get direct download links

🔍 **Example:** `Iron Man`

ADMINS:
• /pm_on - Allow search in PM
• /pm_off - Disable search in PM

📢 Channel: @Sseries_Area
"""
    await message.reply_text(start_text)
    asyncio.create_task(cleanup_old_searches()) # Start cleanup task

@Client.on_message(filters.command("help"))
async def help_bot(bot, message):
    """Help command handler"""
    help_text = """
🆘 Bot Help Guide

🔍 **Search Commands:**
• Just type movie name - `Avengers`
• Use specific keywords - `Avatar 2 1080p`

🎯 **Features:**
• Search any movie
• Movie posters
• Dynamic buttons for Watch, Drive, & Quality
• Paginated "Other" links
• Multi-page navigation

📱 **Supported Cloud Services:**
• GoFile, StreamTape, HubDrive
• GDFlix, GDTot, VikingFile, FilePress
• And many more...

❓ Need Help? Contact support or check @Sseries_Area
"""
    await message.reply_text(help_text)

@Client.on_message(filters.command("stats"))
async def bot_stats(bot, message):
    """Show bot statistics"""
    active_searches = len(user_searches)
    pm_status = "✅ Enabled" if PM_ENABLED else "❌ Disabled"
    
    stats_text = f"""
📊 Bot Statistics

👥 Active Searches (Cached): {active_searches}
🤖 PM Search Status: {pm_status}
🔍 Search Engine: SkyMoviesHD
📢 Channel: @Sseries_Area
"""
    await message.reply_text(stats_text)

async def cleanup_old_searches():
    """Clean up old search data"""
    while True:
        try:
            await asyncio.sleep(300)
            current_time = time()
            expired_users = []
            for user_id, data in user_searches.items():
                if current_time - data['timestamp'] > 600:
                    expired_users.append(user_id)
                    
            for user_id in expired_users:
                del user_searches[user_id]
                
            if expired_users:
                print(f"🧹 Cleaned up {len(expired_users)} expired searches")
                
        except Exception as e:
            print(f"❌ Cleanup error: {e}")

print("✅ 'Super-Smart' search bot loaded successfully!")

# Add your Client().run() logic here
# Example:
# app = Client("my_bot", api_id=YOUR_API_ID, api_hash="YOUR_API_HASH", bot_token="YOUR_BOT_TOKEN")
# app.run()
