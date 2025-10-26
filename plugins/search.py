import asyncio
from time import time 
from pyrogram import Client, filters 
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton 
from scraper.skymovies import SkyMoviesScraper

# Store recent searches to avoid re-searching
user_searches = {}

@Client.on_message(filters.text & filters.group & filters.incoming)
async def simple_search(bot, message):
    """Simple search without database dependencies"""
    
    if message.text.startswith("/"):
        return    
    
    query = message.text 
    
    try:
        # Search movies
        scraper = SkyMoviesScraper()
        movies = await scraper.search_movies(query)
        
        if not movies:
            await message.reply_text("❌ No movies found. Try different keywords.")
            return
        
        # Store movies for this user
        user_searches[message.from_user.id] = {
            'movies': movies,
            'timestamp': time()
        }
        
        # Create results text
        results_text = f"**🔍 Search Results for '{query}':**\n\n"
        for i, movie in enumerate(movies, 1):
            results_text += f"**{i}. {movie['title']}**\n\n"
        
        results_text += "__Powered By @Sseries_Area__"
        
        # Create buttons with movie indices
        buttons = []
        row = []
        for i, movie in enumerate(movies, 1):
            callback_data = f"mov_{i}"  # Use index instead of URL
            
            row.append(InlineKeyboardButton(
                f"🎬 Option {i}", 
                callback_data=callback_data
            ))
            
            if i % 3 == 0:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        # Add a refresh button
        buttons.append([InlineKeyboardButton("🔄 Refresh Search", callback_data="refresh")])
        
        msg = await message.reply_text(
            text=results_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        await message.reply_text("❌ Search temporarily unavailable.")

@Client.on_callback_query(filters.regex(r"^mov_"))
async def show_download_links(bot, update):
    """Show download links for selected movie"""
    try:
        user_id = update.from_user.id
        movie_index = int(update.data.split("_", 1)[1]) - 1  # Convert to 0-based index
        
        # Get stored movies for this user
        user_data = user_searches.get(user_id)
        if not user_data or time() - user_data['timestamp'] > 300:  # 5 minutes expiry
            await update.answer("❌ Search expired. Please search again.", show_alert=True)
            return
        
        movies = user_data['movies']
        
        if movie_index >= len(movies):
            await update.answer("❌ Invalid selection", show_alert=True)
            return
        
        selected_movie = movies[movie_index]
        movie_url = selected_movie['url']
        
        await update.answer("⏳ Loading download links...")
        
        # Get movie details
        scraper = SkyMoviesScraper()
        movie_details = await scraper.get_movie_details(movie_url)
        
        if not movie_details or not movie_details.get('download_links'):
            await update.answer("❌ No download links found", show_alert=True)
            return
        
        movie_title = movie_details['title']
        download_links = movie_details['download_links']
        
        # Create download links message with IMPROVED formatting
        message_text = f"**📌 {movie_title}**\n\n"
        
        # Define display order for categories
        display_order = [
            ('gdrive', '🐬 Google Drive'),
            ('terabox', '📦 TeraBox'), 
            ('mediafire', '🔥 MediaFire'),
            ('mega', '🌀 MEGA'),
            ('gofile', '📁 GoFile'),
            ('streamtape', '🎥 StreamTape'),
            ('pixeldrain', '💧 PixelDrain'),
            ('watch_online', '👀 Watch Online'),
            ('other', '🔗 Other Links')
        ]
        
        links_found = False
        
        for category_key, display_name in display_order:
            if download_links.get(category_key):
                message_text += f"**{display_name}:**\n"
                for link in download_links[category_key][:3]:  # Max 3 per category
                    message_text += f"• {link}\n"
                message_text += "\n"
                links_found = True
        
        # If no links found
        if not links_found:
            message_text += "❌ No download links found on this page.\n\n"
            message_text += "💡 *Try clicking the movie link directly on the website*:\n"
            message_text += f"🌐 {movie_url}\n\n"
        
        # Add statistics
        total_links = sum(len(links) for links in download_links.values())
        if total_links > 0:
            message_text += f"**📊 Total Links Found:** {total_links}\n\n"
        
        message_text += f"__Powered By @Sseries_Area__"
        
        # Create buttons
        buttons = [
            [InlineKeyboardButton("🔙 Back to Results", callback_data="back_results")],
            [InlineKeyboardButton("🔄 Search Again", callback_data="new_search")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ]
        
        # Try to send with poster if available
        poster = movie_details.get('poster')
        if poster:
            try:
                await update.message.reply_photo(
                    photo=poster,
                    caption=message_text,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                await update.message.delete()
            except:
                await update.message.edit_text(
                    text=message_text,
                    disable_web_page_preview=False,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
        else:
            await update.message.edit_text(
                text=message_text,
                disable_web_page_preview=False,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        await update.answer("✅ Download links loaded!")
        
    except Exception as e:
        print(f"❌ Download links error: {e}")
        await update.answer("❌ Error loading download links", show_alert=True)

@Client.on_callback_query(filters.regex(r"^back_results$"))
async def back_to_results(bot, update):
    """Go back to search results"""
    try:
        user_id = update.from_user.id
        user_data = user_searches.get(user_id)
        
        if not user_data:
            await update.answer("❌ No previous search found", show_alert=True)
            return
        
        movies = user_data['movies']
        
        # Recreate results text
        results_text = "**🔍 Your Previous Search Results:**\n\n"
        for i, movie in enumerate(movies, 1):
            results_text += f"**{i}. {movie['title']}**\n\n"
        
        results_text += "__Powered By @Sseries_Area__"
        
        # Recreate buttons
        buttons = []
        row = []
        for i, movie in enumerate(movies, 1):
            callback_data = f"mov_{i}"
            row.append(InlineKeyboardButton(f"🎬 Option {i}", callback_data=callback_data))
            
            if i % 3 == 0:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        buttons.append([InlineKeyboardButton("🔄 Refresh Search", callback_data="refresh")])
        
        await update.message.edit_text(
            text=results_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        await update.answer("↩️ Back to results")
        
    except Exception as e:
        print(f"❌ Back to results error: {e}")
        await update.answer("❌ Error going back", show_alert=True)

@Client.on_callback_query(filters.regex(r"^refresh$"))
async def refresh_search(bot, update):
    """Refresh the search results"""
    try:
        original_text = update.message.text
        # Extract query from original message
        if "Search Results for '" in original_text:
            query = original_text.split("Search Results for '")[1].split("'")[0]
            
            await update.answer("🔄 Refreshing search...")
            
            # Perform new search
            scraper = SkyMoviesScraper()
            movies = await scraper.search_movies(query)
            
            if not movies:
                await update.answer("❌ No movies found after refresh", show_alert=True)
                return
            
            # Update stored movies
            user_searches[update.from_user.id] = {
                'movies': movies,
                'timestamp': time()
            }
            
            # Update results text
            results_text = f"**🔍 Search Results for '{query}' (Refreshed):**\n\n"
            for i, movie in enumerate(movies, 1):
                results_text += f"**{i}. {movie['title']}**\n\n"
            
            results_text += "__Powered By @Sseries_Area__"
            
            # Update buttons
            buttons = []
            row = []
            for i, movie in enumerate(movies, 1):
                callback_data = f"mov_{i}"
                row.append(InlineKeyboardButton(f"🎬 Option {i}", callback_data=callback_data))
                
                if i % 3 == 0:
                    buttons.append(row)
                    row = []
            
            if row:
                buttons.append(row)
            
            buttons.append([InlineKeyboardButton("🔄 Refresh Again", callback_data="refresh")])
            
            await update.message.edit_text(
                text=results_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
            await update.answer("✅ Search refreshed!")
            
    except Exception as e:
        print(f"❌ Refresh error: {e}")
        await update.answer("❌ Error refreshing search", show_alert=True)

@Client.on_callback_query(filters.regex(r"^new_search$"))
async def new_search_prompt(bot, update):
    """Prompt for new search"""
    await update.message.edit_text(
        "**🔍 Enter your movie name to search:**\n\nExample: `Avengers Endgame`\n\n__Powered By @Sseries_Area__"
    )
    await update.answer("🔍 Ready for new search")

@Client.on_callback_query(filters.regex(r"^close$"))
async def close_message(bot, update):
    """Close message"""
    try:
        await update.message.delete()
        # Clean up user data
        user_id = update.from_user.id
        if user_id in user_searches:
            del user_searches[user_id]
    except:
        pass

# Clean up old searches periodically
async def cleanup_old_searches():
    while True:
        try:
            current_time = time()
            expired_users = []
            for user_id, data in user_searches.items():
                if current_time - data['timestamp'] > 600:  # 10 minutes
                    expired_users.append(user_id)
            
            for user_id in expired_users:
                del user_searches[user_id]
            
            await asyncio.sleep(300)  # Run every 5 minutes
        except:
            await asyncio.sleep(60)

# Start cleanup task when bot starts
@Client.on_message(filters.command("start"))
async def start_bot(bot, message):
    asyncio.create_task(cleanup_old_searches())
    await message.reply_text("🤖 Movie Search Bot is running!\n\nJust type any movie name to search.")
