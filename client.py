from info import *
from pyrogram import Client

# User = Client(name="user", session_string=SESSION)  # ← IS LINE KO COMMENT KARO

class Bot(Client):   
    def __init__(self):
        super().__init__(   
           "bot",
            api_id=API_ID,
            api_hash=API_HASH,           
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"})
    
    async def start(self):                        
        await super().start()        
        # await User.start()  # ← IS LINE KO BHI COMMENT KARO
        print("🤖 Bot Started Successfully!")   
    
    async def stop(self, *args):
        await super().stop()
        print("Bot Stopped!")
