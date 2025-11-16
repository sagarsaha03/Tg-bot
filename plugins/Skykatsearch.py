import asyncio
from time import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified
from scraper.skymovies import SkyMoviesScraper
from scraper.katmoviefix import KatMovieFixScraper
import re
import math

# Global state
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
        elif 'new7.gdflix.net/file/' in url:
            match = re.search(r'new7.gdflix.net/file/([a-zA-Z0-9]+)', url)
            if match: return f"https://new7.gdflix.net/file/{match.group(1)}"
        elif 'dumbalag.com/' in url:
            match = re.search(r'dumbalag.com/([a-zA-Z0-9]+)', url)
            if match: return f"https://dumbalag.com/{match.group(1)}"
    return url

def build_main_links_message(user_data):
    """Build message for download links"""
    movie_title = user_data.get('current_movie_title', 'Unknown Movie')
    download_links = user_data.get('main_links', {})
    button_links = user_data.get('button_links', {})
    
    # Store button links
    user_data['button_links_list'] = list(button_links.items())

    # Category pagination
    available_categories = []
    
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
    
    # Add ordered categories first
    for key, name in display_order:
        if download_links.get(key):
            available_categories.append((key, name))
            
    # Add 'other' category
    if download_links.get('other'):
        available_categories.append(('other', '🔗 Other Drive Links'))
        
    # Add any other categories
    ordered_keys = [k[0] for k in available_categories]
    for key, links in download_links.items():
        if key not in ordered_keys and links:
            available_categories.append((key, f"🔗 {key.title()} Links"))

    # Paginate categories
    category_page = user_data.get('category_page', 1)
    categories_per_page = 4
    total_categories = len(available_categories)
    total_category_pages = math.ceil(total_categories / categories_per_page)
    
    start_index = (category_page - 1) * categories_per_page
    end_index = start_index + categories_per_page
    current_categories_chunk = available_categories[start_index:end_index]
    
    user_data['total_category_pages'] = total_category_pages

    # Build caption
    caption_text = f"📌 **{movie_title}**\n\n"
    links_found_on_this_page = False
    
    for category_key, display_name in current_categories_chunk:
        links = download_links.get(category_key, [])
        if links:
            caption_text += f"**{display_name}**\n"
            links_found_on_this_page = True
            shown_links = set()
            for link in links:
                display_link = shorten_url_display(link)
                if display_link not in shown_links:
                    shown_links.add(display_link)
                    caption_text += f"• {display_link}\n"
            caption_text += "\n"

    if not links_found_on_this_page:
        if category_page == 1 and total_categories == 0:
             caption_text += "❌ No direct download links were found.\n\n"
        else:
             caption_text += "• No more links on this page.\n\n"

    caption_text += "Powered By @Sseries_Area"
    
    # Build buttons
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

    # Category pagination button
    category_buttons = []
    if total_category_pages > 1:
        next_page = category_page + 1
        if next_page > total_category_pages:
            next_page = 1
        
        category_buttons.append(
            InlineKeyboardButton(
                f"🔄 Refresh Links {category_page}/{total_category_pages}", 
                callback_data=f"category_page_{next_page}"
            )
        )
    if category_buttons:
        buttons.append(category_buttons)

    # Navigation buttons
    buttons.extend([
        [InlineKeyboardButton("🔙 Back to Results", callback_data="back_results")],
        [InlineKeyboardButton("🔄 Search Again", callback_data="new_search")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])
    
    return caption_text, InlineKeyboardMarkup(buttons)

@Client.on_message(filters.text & (filters.group | filters.private) & filters.incoming)
async def handle_source_selection(bot, message):
    """Handle search query and show source selection"""
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
        # Show source selection
        source_text = f"🔍 **Search Query:** `{query}`\n\n**Please select a source to search:**"
        
        buttons = [
            [
                InlineKeyboardButton("🎬 SkyMovies", callback_data=f"src_sky_{query}"),
                InlineKeyboardButton("🎯 KatMovieFix", callback_data=f"src_kat_{query}")
            ],
            [
                InlineKeyboardButton("🌐 Search All Sources", callback_data=f"src_all_{query}")
            ]
        ]
        
        await message.reply_text(
            text=source_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"❌ Source selection error: {e}")
        await message.reply_text("❌ Error processing your request.")

@Client.on_callback_query(filters.regex(r"^src_"))
async def handle_source_callback(bot, update):
    """Handle source selection"""
    try:
        user_id = update.from_user.id
        data_parts = update.data.split('_')
        source = data_parts[1]  # sky, kat, all
        query = '_'.join(data_parts[2:])  # Original query
        
        await update.answer(f"⏳ Searching on {source}...")
        
        search_msg = await update.message.edit_text(f"🔍 Searching on {'SkyMovies' if source == 'sky' else 'KatMovieFix' if source == 'kat' else 'all sources'}...")
        
        all_movies = []
        
        if source in ['sky', 'all']:
            print(f"🔍 [Source] Searching SkyMovies for: {query}")
            sky_scraper = SkyMoviesScraper()
            sky_movies = await sky_scraper.get_all_search_results(query)
            await sky_scraper.close_session()
            for movie in sky_movies:
                movie['source'] = 'sky'
                all_movies.append(movie)
            print(f"✅ [Source] SkyMovies found: {len(sky_movies)} results")
        
        if source in ['kat', 'all']:
            print(f"🔍 [Source] Searching KatMovieFix for: {query}")
            kat_scraper = KatMovieFixScraper()
            kat_movies = await kat_scraper.get_all_search_results(query)
            await kat_scraper.close_session()
            for movie in kat_movies:
                movie['source'] = 'kat'
                all_movies.append(movie)
            print(f"✅ [Source] KatMovieFix found: {len(kat_movies)} results")
        
        print(f"📊 [Source] Total results: {len(all_movies)}")
        
        if not all_movies:
            await search_msg.edit_text(f"❌ No results found for '{query}'.")
            return
            
        # Store in user data
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
            'total_results': total_results,
            'source': source  # Store selected source
        }
        
        # Show results
        await show_search_results(bot, update.message, user_id, current_page)
        
    except Exception as e:
        print(f"❌ Source callback error: {e}")
        await update.message.edit_text("❌ Error during search.")

async def show_search_results(bot, message, user_id, page=1):
    """Show search results with pagination"""
    try:
        user_data = user_searches.get(user_id)
        if not user_data:
            return
            
        all_movies = user_data['all_movies']
        query = user_data['query']
        source = user_data['source']
        
        results_per_page = 4
        total_results = len(all_movies)
        total_pages = (total_results + results_per_page - 1) // results_per_page
        
        if page < 1 or page > total_pages:
            return
            
        current_page = page
        start_index = (current_page - 1) * results_per_page
        end_index = start_index + results_per_page
        current_movies = all_movies[start_index:end_index]
        
        # Update user data
        user_data.update({
            'current_movies': current_movies,
            'current_page': current_page
        })
        
        start_num = start_index + 1
        
        # Build results text with source emojis
        source_name = {
            'sky': 'SkyMovies',
            'kat': 'KatMovieFix', 
            'all': 'All Sources'
        }.get(source, 'Unknown')
        
        results_text = f"🔍 **{source_name}** Results for '{query}'\n"
        results_text += f"📄 Page {current_page}/{total_pages} | Total: {total_results}\n\n"
        
        for i, movie in enumerate(current_movies, start_num):
            source_emoji = "🎬" if movie['source'] == 'sky' else "🎯"
            title = movie['title'][:60] + "..." if len(movie['title']) > 60 else movie['title']
            results_text += f"{i}. {source_emoji} {title}\n\n"
        
        results_text += "Powered By @Sseries_Area"
        
        # Build buttons
        buttons = []
        row = []
        for i, movie in enumerate(current_movies, start_num):
            source_emoji = "🎬" if movie['source'] == 'sky' else "🎯"
            row.append(InlineKeyboardButton(f"{source_emoji} {i}", callback_data=f"mov_{i}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        
        # Pagination buttons
        pagination_buttons = []
        if current_page > 1:
            pagination_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{current_page-1}"))
        if current_page < total_pages:
            pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{current_page+1}"))
        
        if pagination_buttons:
            buttons.append(pagination_buttons)
        
        # Source change button
        buttons.append([InlineKeyboardButton("🔄 Change Source", callback_data=f"change_src_{query}")])
        
        # Edit the message
        await message.edit_text(
            text=results_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"❌ Show results error: {e}")

@Client.on_callback_query(filters.regex(r"^page_"))
async def handle_pagination(bot, update):
    """Handle pagination"""
    try:
        user_id = update.from_user.id
        page = int(update.data.split('_')[1])
        
        await update.answer()
        await show_search_results(bot, update.message, user_id, page)
        
    except Exception as e:
        print(f"❌ Pagination error: {e}")
        await update.answer("❌ Error changing page", show_alert=True)

@Client.on_callback_query(filters.regex(r"^change_src_"))
async def handle_change_source(bot, update):
    """Handle change source request"""
    try:
        user_id = update.from_user.id
        query = update.data.split('change_src_')[1]
        
        await update.answer()
        
        # Show source selection again
        source_text = f"🔍 **Search Query:** `{query}`\n\n**Please select a source to search:**"
        
        buttons = [
            [
                InlineKeyboardButton("🎬 SkyMovies", callback_data=f"src_sky_{query}"),
                InlineKeyboardButton("🎯 KatMovieFix", callback_data=f"src_kat_{query}")
            ],
            [
                InlineKeyboardButton("🌐 Search All Sources", callback_data=f"src_all_{query}")
            ]
        ]
        
        await update.message.edit_text(
            text=source_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"❌ Change source error: {e}")
        await update.answer("❌ Error changing source", show_alert=True)

@Client.on_callback_query(filters.regex(r"^mov_"))
async def show_download_links(bot, update):
    """Show download links for selected movie"""
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
        source = selected_movie['source']  # 'sky' or 'kat'
        
        await update.answer("⏳ Loading download links...")
        
        try:
            await update.message.delete()
        except Exception:
            pass 
            
        processing_msg = await bot.send_message(
            chat_id=update.message.chat.id,
            text="🔄 Processing download links...\n\nThis may take 10-15 seconds."
        )
            
        movie_details = None
        
        try:
            if source == 'sky':
                scraper = SkyMoviesScraper()
                movie_details = await scraper.get_movie_details(movie_url)
                await scraper.close_session()
            else:
                scraper = KatMovieFixScraper()
                movie_details = await scraper.get_movie_details(movie_url)
                await scraper.close_session()
        except Exception as e:
            print(f"❌ get_movie_details failed: {e}")
        
        if not movie_details or (not movie_details.get('main_links') and not movie_details.get('button_links')):
            await processing_msg.edit_text("❌ No download links found for this movie.")
            return
            
        user_data['current_movie_title'] = movie_details['title']
        user_data['current_movie_url'] = movie_details['url']
        user_data['poster'] = movie_details.get('poster')
        user_data['main_links'] = movie_details.get('main_links', {})
        user_data['button_links'] = movie_details.get('button_links', {})
        user_data['category_page'] = 1
        user_data['source'] = source
        
        caption, buttons = build_main_links_message(user_data)
        
        # Add source indicator
        source_name = "SkyMovies" if source == 'sky' else "KatMovieFix"
        caption = caption.replace("📌", f"📌 [{source_name}]")
        
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
    """Handle dynamic button clicks"""
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

        button_text, url = button_links_list[button_index]
        movie_title = user_data.get('current_movie_title', 'Unknown Movie')
        source = user_data.get('source', 'sky')
        
        await update.answer(f"⏳ Loading: {button_text}")
        
        source_name = "SkyMovies" if source == 'sky' else "KatMovieFix"
        
        message_text = f"📌 **[{source_name}]** {movie_title}\n\n"
        message_text += f"🌐 **{button_text}** 📥\n\n"
        message_text += f"• {shorten_url_display(url)}\n\n"
        message_text += "Powered By @Sseries_Area"
        
        buttons = [
            [InlineKeyboardButton("🔙 Back to Main Links", callback_data="back_to_main")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ]
        
        await update.message.edit_text(
            text=message_text,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
            
    except Exception as e:
        print(f"❌ Dynamic button click error: {e}")
        await update.answer("❌ Error loading link", show_alert=True)

@Client.on_callback_query(filters.regex(r"^category_page_"))
async def paginate_category_links(bot, update):
    """Handle category pagination"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        if not user_data:
            await update.answer("❌ Search expired.", show_alert=True)
            return

        new_page = int(update.data.split('_')[-1])
        user_data['category_page'] = new_page
        
        caption, buttons = build_main_links_message(user_data)
        
        # Update source indicator
        source = user_data.get('source', 'sky')
        source_name = "SkyMovies" if source == 'sky' else "KatMovieFix"
        caption = caption.replace("📌", f"📌 [{source_name}]")
        
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
        await update.answer("❌ Error loading page", show_alert=True)

@Client.on_callback_query(filters.regex(r"^back_to_main$"))
async def handle_back_to_main(bot, update):
    """Handle back to main links"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        if not user_data:
            await update.answer("❌ Search expired.", show_alert=True)
            return

        caption, buttons = build_main_links_message(user_data)
        
        # Update source indicator
        source = user_data.get('source', 'sky')
        source_name = "SkyMovies" if source == 'sky' else "KatMovieFix"
        caption = caption.replace("📌", f"📌 [{source_name}]")
        
        await update.message.edit_text(
            text=caption,
            reply_markup=buttons,
            disable_web_page_preview=True
        )
        
        await update.answer("🔙 Back to main links")
        
    except Exception as e:
        print(f"❌ Back to main error: {e}")
        await update.answer("❌ Error", show_alert=True)

@Client.on_callback_query(filters.regex(r"^back_results$"))
async def handle_back_results(bot, update):
    """Handle back to results"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        if not user_data:
            await update.answer("❌ Search expired.", show_alert=True)
            return

        await show_search_results(bot, update.message, user_id, user_data.get('current_page', 1))
        await update.answer("🔙 Back to results")
        
    except Exception as e:
        print(f"❌ Back to results error: {e}")
        await update.answer("❌ Error", show_alert=True)

@Client.on_callback_query(filters.regex(r"^new_search$"))
async def handle_new_search(bot, update):
    """Handle new search"""
    try:
        await update.answer("🔄 Starting new search...")
        
        # Show simple message to start new search
        await update.message.edit_text(
            text="🔄 **New Search**\n\nPlease send me the movie name you want to search for.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="close")]
            ])
        )
        
    except Exception as e:
        print(f"❌ New search error: {e}")
        await update.answer("❌ Error", show_alert=True)

@Client.on_callback_query(filters.regex(r"^close$"))
async def handle_close(bot, update):
    """Handle close button"""
    try:
        await update.message.delete()
        await update.answer("❌ Closed")
    except Exception as e:
        await update.answer("❌ Error closing", show_alert=True)
