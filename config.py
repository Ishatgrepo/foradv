from os import environ 

class Config:
    API_ID = environ.get("API_ID", "25121213")
    API_HASH = environ.get("API_HASH", "b734dcc45da130a8156e2be836594706")
    BOT_TOKEN = environ.get("BOT_TOKEN", "7483848628:AAH854QoJTYL1IepQwr4FW5W7v6mygtgwZI") 
    BOT_SESSION = environ.get("BOT_SESSION", "Hope") 
    DATABASE_URI = environ.get("DATABASE", "mongodb+srv://forwww1:evT7SPWK0lSOk11U@cluster0.fuhwp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DATABASE_NAME = environ.get("DATABASE_NAME", "for")
    BOT_OWNER_ID = [int(id) for id in environ.get("BOT_OWNER_ID", '6469067345').split()]

class temp(object): 
    lock = {}
    CANCEL = {}
    forwardings = 0
    BANNED_USERS = []
    IS_FRWD_CHAT = []
