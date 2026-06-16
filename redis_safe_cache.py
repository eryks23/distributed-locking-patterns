import fakeredis
import time
import warnings
from colorama import Fore, Style, init


init(autoreset=True)
warnings.filterwarnings("ignore", category=DeprecationWarning)

server = fakeredis.FakeServer()
r = fakeredis.FakeRedis(server=server, decode_responses=True)


def get_user_data_safe(user_id):
    cache_key = f"user:profile:{user_id}"
    lock_key = f"lock:profile:{user_id}"
    

    while True:
        cache_data = r.hgetall(cache_key)
        
        if cache_data:
            print(f"{Fore.GREEN}[CACHE HIT]{Style.RESET_ALL} Data for {user_id} retrieved from cache.")
            return cache_data
        
        set_lock_key = r.set(lock_key, "locked", nx=True, ex=5)
        
        if set_lock_key:
            try:
                print(f"{Fore.CYAN}[DB FETCH]{Style.RESET_ALL} Fetching data for {Fore.YELLOW}{user_id}{Style.RESET_ALL} from database...")
                
                db_data = {"id": user_id, "name": "ProPlayer123", "level": "99"}
                time.sleep(1)
                
                r.hset(cache_key, mapping=db_data)
                r.expire(cache_key, 60)
                
                print(f"{Fore.MAGENTA}[CACHE SET]{Style.RESET_ALL} Data saved to Redis.")
                return db_data
            
            finally:
                r.delete(lock_key)
                
        else:
            print(f"{Fore.RED}[LOCK WAIT]{Style.RESET_ALL} Another process is fetching data... waiting.")
            time.sleep(0.2)
            
if __name__ == "__main__":
    user_id = "pro_player"
    
    print(f"\n{Fore.WHITE}{Style.BRIGHT}--- START CACHE TEST ---{Style.RESET_ALL}\n")
    
    res1 = get_user_data_safe(user_id)
    print(f"Result 1: {res1}\n")
    
    res2 = get_user_data_safe(user_id)
    print(f"Result 2: {res2}\n")

    print(f"{Fore.WHITE}{Style.BRIGHT}--- END OF TEST ---{Style.RESET_ALL}")
