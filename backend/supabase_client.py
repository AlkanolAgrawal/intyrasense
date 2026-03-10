import os
from dotenv import load_dotenv
from supabase import create_client, Client


# ---------------------------------
# LOAD ENV
# ---------------------------------
load_dotenv()


# ---------------------------------
# ENV VALIDATION
# ---------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL environment variable not set")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY environment variable not set")


# ---------------------------------
# CLIENT INITIALIZATION
# ---------------------------------
def create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------------------------------
# GLOBAL CLIENT (singleton)
# ---------------------------------
supabase: Client = create_supabase_client()