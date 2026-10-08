import requests
import time

print("""
FORZA
""")

BASE_URL = "http://wolfteamklan.joygame.com/Ranking/GetRanking"
DATA_FILE = "RÜTBELİ.txt"


def fetch_players_until_empty(start_index, limit, rank_type=1, order_type=1):
    count = 0

    try:
        while True:
            params = {
                "RankType": rank_type,
                "OrderType": order_type,
                "StartIndex": start_index
            }

            response = requests.get(BASE_URL, params=params)
            response.raise_for_status()

            data = response.json()
            users = data.get("Data", [])

            if not users:
                print("Veri bitti.")
                break

            for user in users:

                if count >= limit:
                    print(f"\nToplam {limit} ID çekildi.")
                    return

                account = user.get("Account", "N/A")

                count += 1

                print(f"{count}. {account}")

                with open(DATA_FILE, "a", encoding="utf-8") as file:
                    file.write(f"{account}\n")

                time.sleep(0)

            start_index += 1

    except requests.exceptions.RequestException as e:
        print(f"API isteği başarısız: {e}")


def main():
    start_index = int(input("Başlangıç indexini girin: "))
    limit = int(input("Kaç adet ID çekilsin?: "))

    fetch_players_until_empty(start_index, limit)


if __name__ == "__main__":
    main()