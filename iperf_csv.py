import re
import csv
import os

def parse_single_udp_client(file_path):
    """
    Parsuje raport serwera znajdujący się w logu klienta (UDP).
    Szuka linii z podsumowaniem, która zawiera statystyki zwrotne.
    """
    if not os.path.exists(file_path):
        return None

    # Regex szukający linii z danymi: [ ID] Interval Transfer Bandwidth Jitter Lost/Total Latency
    # Skupiamy się na wyciągnięciu wartości liczbowych
    # Przykład: [  1] 0.00-60.15 sec 44.8 MBytes 6.25 Mbits/sec 0.578 ms 115/32102 (0.36%) 114.678/ ...
    data_pattern = re.compile(
        r"\[\s*\d+\]\s+\d+\.\d+-\d+\.\d+\s+sec\s+[\d.]+\s+\w+Bytes\s+"
        r"([\d.]+)\s+\w+bits/sec\s+"  # 1: Bandwidth
        r"([\d.]+)\s+ms\s+"           # 2: Jitter
        r"(\d+/\d+)\s+"               # 3: Lost/Total
        r"\(([\d.e+]+)%\)\s+"         # 4: Loss %
        r"([\d.]+)/"                  # 5: Latency Avg
    )

    result = {
        "bandwidth": "POPRAW",
        "jitter_ms": "POPRAW",
        "loss_percent": "POPRAW",
        "latency_avg_ms": "POPRAW"
    }

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Szukamy wszystkich dopasowań, ale bierzemy ostatnie (raport serwera jest na końcu)
            matches = list(data_pattern.finditer(content))
            if matches:
                last_match = matches[-1]
                result["bandwidth"] = last_match.group(1)
                result["jitter_ms"] = last_match.group(2)
                result["loss_percent"] = last_match.group(4)
                result["latency_avg_ms"] = last_match.group(5)
                return result
    except Exception:
        pass
    
    return result
def parse_iperf_tcp(file_path):
    """
    Precyzyjnie wyciąga Bandwidth i Retransmisje (Rtry) przy użyciu Regex.
    """
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Szukamy linii z wynikami. 
            # Grupa 1: Bandwidth (np. 3.62)
            # Grupa 2: Jednostka (np. Mbits/sec)
            # Grupa 3: Write/Err (np. 208/0) -> ignorujemy
            # Grupa 4: Retransmisje (np. 65) -> TO NAS INTERESUJE
            tcp_pattern = re.compile(
                r"([\d.]+)\s+(\w+bits/sec)\s+"  # Bandwidth + jednostka
                r"(\d+/\d+)\s+"                 # Write/Err (np. 208/0)
                r"(\d+)\s+"                     # Retransmisje (Rtry - np. 65)
                r"[\d\w/]+"                     # Cwnd/RTT...
            )
            
            matches = list(tcp_pattern.finditer(content))
            if matches:
                # Bierzemy ostatnie dopasowanie (podsumowanie całego testu)
                last_match = matches[-1]
                return {
                    "bandwidth": last_match.group(1),
                    "retransmissions": last_match.group(4) # Grupa 4 to Rtry
                }
    except Exception as e:
        print(f"Błąd przy parsowaniu TCP w {file_path}: {e}")
        
    return {"bandwidth": "POPRAW", "retransmissions": "POPRAW"}

if __name__ == "__main__":
    all_data = []
    
    for i in range(1, 11):
        folder_name = str(i)
        if not os.path.exists(folder_name):
            continue
            
        print(f"Przetwarzanie folderu: {folder_name}")

        # 1. Parsowanie plików UDP dla hostów h1-h7
        for h_num in range(1, 8):
            host_id = f"h{h_num}"
            udp_filename = f"{host_id}_udp_iperf.txt"
            udp_path = os.path.join(folder_name, udp_filename)
            
            udp_metrics = parse_single_udp_client(udp_path)
            
            # Jeśli plik istnieje, dodajemy dane (nawet jeśli są to POPRAW)
            if os.path.exists(udp_path):
                all_data.append({
                    "run": i,
                    "host": host_id,
                    "protocol": "UDP",
                    "bandwidth": udp_metrics["bandwidth"],
                    "jitter_ms": udp_metrics["jitter_ms"],
                    "loss_percent": udp_metrics["loss_percent"],
                    "latency_avg_ms": udp_metrics["latency_avg_ms"],
                    "retransmissions": 0
                })

        # 2. Parsowanie TCP (h1)
        tcp_path = os.path.join(folder_name, 'h1_tcp_iperf.txt')
        if os.path.exists(tcp_path):
            tcp_metrics = parse_iperf_tcp(tcp_path)
            all_data.append({
                "run": i,
                "host": "h1",
                "protocol": "TCP",
                "bandwidth": tcp_metrics["bandwidth"],
                "jitter_ms": "0",
                "loss_percent": "0",
                "latency_avg_ms": "0",
                "retransmissions": tcp_metrics["retransmissions"]
            })

    # Zapis do CSV
    csv_file = "wyniki_eksperymentu.csv"
    fieldnames = ["run", "host", "protocol", "bandwidth", "jitter_ms", "loss_percent", "latency_avg_ms", "retransmissions"]
    
    with open(csv_file, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_data)

    print(f"\nProces zakończony. Wyniki w: {csv_file}")