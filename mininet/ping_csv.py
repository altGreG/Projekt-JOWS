import re
import csv
import os

def parse_ping_h7(file_path):
    """
    Parsuje plik h7_ping.txt i wyciąga statystyki.
    """
    if not os.path.exists(file_path):
        return None

    results = {
        "loss_percent": "POPRAW",
        "rtt_avg": "POPRAW",
        "rtt_mdev": "POPRAW"
    }

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

            # 1. Procent strat
            loss_match = re.search(r"([\d.]+)%\s+packet\s+loss", content)
            if loss_match:
                results["loss_percent"] = loss_match.group(1)

            # 2. Średni RTT i MDEV (jitter)
            # Szukamy wzorca: min/avg/max/mdev = 9.073/115.827/139.227/16.846
            rtt_match = re.search(r"rtt\s+min/avg/max/mdev\s+=\s+[\d.]+/([\d.]+)/[\d.]+/([\d.]+)\s+ms", content)
            if rtt_match:
                results["rtt_avg"] = rtt_match.group(1)
                results["rtt_mdev"] = rtt_match.group(2)
                
    except Exception:
        pass

    return results

if __name__ == "__main__":
    all_ping_data = []
    
    # Przechodzimy przez foldery 1-10
    for i in range(1, 11):
        folder = str(i)
        if not os.path.exists(folder):
            continue
            
        print(f"Folder {folder:2}: Przetwarzanie h7_ping.txt...", end=" ")
        
        path = os.path.join(folder, "h7_ping.txt")
        stats = parse_ping_h7(path)
        
        if stats:
            all_ping_data.append({
                "run": i,
                "host": "h7",
                "loss_percent": stats["loss_percent"],
                "rtt_avg": stats["rtt_avg"],
                "rtt_mdev": stats["rtt_mdev"]
            })
            print("OK")
        else:
            print("BRAK PLIKU")

    # Zapis do CSV
    output_file = "wyniki_ping_h7.csv"
    with open(output_file, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["run", "host", "loss_percent", "rtt_avg", "rtt_mdev"])
        writer.writeheader()
        writer.writerows(all_ping_data)

    print(f"\nGotowe! Wyniki dla h7 zapisano w: {output_file}")