"""
Generator data sintetis: Bengkel Resmi Toyota Medan
"Smart Workshop Intelligence" - data penunjang analisis survival / market basket / demand forecast.

Generating process ditata eksplisit supaya 3 analisis punya sinyal:
- Survival: interval ganti oli bergantung engine, oli, segmen pemakaian (km/bulan).
- Market basket: item per kunjungan punya struktur asosiasi yang dibangun sengaja.
- Demand forecast: tanggal kunjungan punya pola hari, pasca-gajian, pra-Lebaran, libur.
"""
import numpy as np
import pandas as pd
from datetime import date, timedelta

RNG = np.random.default_rng(42)

WINDOW_START = date(2022, 1, 1)
WINDOW_END   = date(2026, 6, 15)
N_CARS = 620

# ----------------------------------------------------------------------------
# 1. KATALOG TOYOTA INDONESIA (model -> varian, penggerak, bahan bakar, oli, harga oli)
#    drive: FWD / RWD / 4x4 ; fuel: Bensin / Diesel / Hybrid
#    oil_type: Mineral / Semi-Sintetik / Full-Sintetik
#    weight = popularitas (Avanza jadi hero)
# ----------------------------------------------------------------------------
CATALOG = [
    # model, varian, drive, fuel, oil_type, harga_oli_jasa(IDR), bobot
    ("Avanza",        "1.3 E",      "RWD", "Bensin", "Semi-Sintetik", 420000, 14),
    ("Avanza",        "1.5 G",      "FWD", "Bensin", "Semi-Sintetik", 450000, 16),
    ("Avanza",        "1.5 Veloz",  "FWD", "Bensin", "Full-Sintetik", 520000, 10),
    ("Veloz",         "1.5 Q CVT",  "FWD", "Bensin", "Full-Sintetik", 540000,  7),
    ("Rush",          "1.5 S TRD",  "RWD", "Bensin", "Semi-Sintetik", 480000,  8),
    ("Raize",         "1.0 Turbo",  "FWD", "Bensin", "Full-Sintetik", 500000,  6),
    ("Agya",          "1.2 G",      "FWD", "Bensin", "Mineral",       330000,  6),
    ("Calya",         "1.2 G",      "FWD", "Bensin", "Mineral",       330000,  7),
    ("Vios",          "1.5 G",      "FWD", "Bensin", "Full-Sintetik", 510000,  3),
    ("Yaris",         "1.5 S",      "FWD", "Bensin", "Full-Sintetik", 510000,  3),
    ("Innova Reborn", "2.4 V Diesel","RWD","Diesel", "Full-Sintetik", 650000,  7),
    ("Innova Reborn", "2.0 G Bensin","RWD","Bensin", "Semi-Sintetik", 560000,  3),
    ("Innova Zenix",  "2.0 HV",     "FWD", "Hybrid", "Full-Sintetik", 640000,  5),
    ("Fortuner",      "2.4 VRZ 4x2","RWD", "Diesel", "Full-Sintetik", 720000,  5),
    ("Fortuner",      "2.8 GR 4x4", "4x4", "Diesel", "Full-Sintetik", 780000,  3),
    ("Hilux",         "2.4 D-Cab 4x4","4x4","Diesel","Full-Sintetik", 760000,  3),
    ("Yaris Cross",   "1.5 HV",     "FWD", "Hybrid", "Full-Sintetik", 600000,  3),
    ("Corolla Cross", "1.8 HV",     "FWD", "Hybrid", "Full-Sintetik", 640000,  2),
    ("Camry",         "2.5 HV",     "FWD", "Hybrid", "Full-Sintetik", 720000,  1),
]
cat_df = pd.DataFrame(CATALOG, columns=
    ["model","varian","penggerak","bahan_bakar","jenis_oli","harga_oli","bobot"])
cat_w = cat_df["bobot"].to_numpy(float); cat_w /= cat_w.sum()

# interval ganti oli (km) berdasar jenis oli & bahan bakar
def oil_interval_km(fuel, oil_type):
    base = {"Mineral":4500, "Semi-Sintetik":7000, "Full-Sintetik":9500}[oil_type]
    if fuel == "Diesel": base = min(base, 6000)      # diesel lebih sering (soot)
    if fuel == "Hybrid": base = max(base, 10000)     # mesin lebih jarang nyala
    return base

TRANSMISI_BY_MODEL = {  # transmisi dominan
    "Agya":"MT/AT","Calya":"MT/AT","Avanza":"MT/AT","Rush":"AT","Veloz":"CVT",
    "Raize":"CVT","Vios":"CVT","Yaris":"CVT","Innova Reborn":"AT","Innova Zenix":"CVT",
    "Fortuner":"AT","Hilux":"MT/AT","Yaris Cross":"CVT","Corolla Cross":"CVT","Camry":"CVT",
}

# ----------------------------------------------------------------------------
# 2. GEOGRAFI MEDAN + NAMA + TELEPON
# ----------------------------------------------------------------------------
KECAMATAN = [
    ("Medan Kota",20212),("Medan Baru",20153),("Medan Polonia",20157),
    ("Medan Maimun",20151),("Medan Petisah",20111),("Medan Barat",20231),
    ("Medan Timur",20231),("Medan Tembung",20222),("Medan Area",20214),
    ("Medan Denai",20227),("Medan Johor",20144),("Medan Amplas",20148),
    ("Medan Sunggal",20128),("Medan Helvetia",20124),("Medan Selayang",20131),
    ("Medan Tuntungan",20135),("Medan Marelan",20255),("Medan Perjuangan",20233),
    ("Medan Deli",20241),("Medan Labuhan",20252),
]
JALAN = ["Jl. Gatot Subroto","Jl. Sisingamangaraja","Jl. Iskandar Muda","Jl. Setia Budi",
    "Jl. AH Nasution","Jl. Brigjen Katamso","Jl. Gajah Mada","Jl. Ringroad","Jl. Pancing",
    "Jl. Krakatau","Jl. Pemuda","Jl. Adam Malik","Jl. Dr. Mansyur","Jl. Cemara",
    "Jl. SM Raja","Jl. William Iskandar","Jl. Karya Wisata","Jl. Jamin Ginting",
    "Jl. Kapten Muslim","Jl. Marelan Raya","Jl. Pasar Merah","Jl. Halat","Jl. Sutomo",
    "Jl. HM Yamin","Jl. Sekip","Jl. Glugur","Jl. Bromo","Jl. Denai","Jl. Menteng"]
KOMPLEK = ["Komp. Cemara Asri","Komp. Tasbih","Perumahan J City","Komp. Citra Garden",
    "Komp. Royal Sumatra","","","","",""]  # sebagian kosong (alamat jalan biasa)

DEPAN_PRIA = ["Budi","Andi","Rizky","Hendra","Surya","Dedi","Roni","Agus","Fahmi","Indra",
    "Reza","Taufik","Wahyu","Bayu","Dimas","Hadi","Iwan","Joko","Ferry","Eko","Rendi",
    "Maruli","Togar","Pranata","Boy","Edy","Robby","Frans","Gunawan","Hermanto"]
DEPAN_WANITA = ["Siti","Dewi","Rina","Maya","Lestari","Sari","Wati","Ratna","Yuni","Fitri",
    "Nurul","Ayu","Indah","Mega","Putri","Tiur","Rosma","Juliana","Erlina","Santi"]
MARGA_BATAK = ["Siregar","Nasution","Harahap","Lubis","Hutapea","Simanjuntak","Sitorus",
    "Tanjung","Pohan","Sinaga","Situmorang","Pasaribu","Ginting","Sembiring","Tarigan",
    "Purba","Saragih","Damanik","Manurung","Hutabarat","Panjaitan","Silalahi","Marpaung",
    "Rangkuti","Batubara","Dalimunthe","Pulungan"]
NAMA_JAWA  = ["Santoso","Wijaya","Pratama","Wibowo","Susanto","Setiawan","Nugroho","Saputra"]
NAMA_TIONGHOA = ["Tanaka","Wijaya","Halim","Gunawan","Suryadi","Wirawan","Hartono","Salim"]
PREFIX_HP = ["0812","0813","0821","0822","0852","0853","0811","0823","0851","0838","0896"]

def buat_nama():
    r = RNG.random()
    if r < 0.55:   # Batak (dominan di Medan)
        dpn = RNG.choice(DEPAN_PRIA if RNG.random()<0.62 else DEPAN_WANITA)
        return f"{dpn} {RNG.choice(MARGA_BATAK)}"
    elif r < 0.78: # Jawa / nasional
        dpn = RNG.choice(DEPAN_PRIA if RNG.random()<0.6 else DEPAN_WANITA)
        return f"{dpn} {RNG.choice(NAMA_JAWA)}"
    elif r < 0.90: # Tionghoa
        return f"{RNG.choice(DEPAN_PRIA+DEPAN_WANITA)} {RNG.choice(NAMA_TIONGHOA)}"
    else:          # Melayu / satu nama
        return f"{RNG.choice(DEPAN_PRIA)} {RNG.choice(['Effendi','Maulana','Rahman','Hasibuan','Daulay'])}"

def buat_hp():
    return f"{RNG.choice(PREFIX_HP)}{RNG.integers(1000,9999)}{RNG.integers(1000,9999)}"

def buat_alamat():
    komp = RNG.choice(KOMPLEK)
    jln  = RNG.choice(JALAN)
    no   = RNG.integers(1,250)
    if komp:
        blok = f"Blok {RNG.choice(list('ABCDEFG'))}{RNG.integers(1,30)}"
        return f"{komp} {blok}, {jln}"
    return f"{jln} No. {no}"

def buat_nopol():
    # Plat Sumut = BK ; format BK #### XX
    return f"BK {RNG.integers(1000,9999)} {''.join(RNG.choice(list('ABCDEFGHJKLMNPRSTUVWXYZ'),2))}"

# ----------------------------------------------------------------------------
# 3. SEGMEN PEMAKAIAN (hidden ground truth untuk validasi clustering)
#    km/bulan + faktor severity (kondisi berat) berbeda per segmen
# ----------------------------------------------------------------------------
SEGMEN = ["Light Commuter","Heavy Daily","Weekend Warrior"]
SEG_P  = [0.45, 0.35, 0.20]
def km_per_bulan(seg):
    if seg=="Light Commuter":  return float(np.clip(RNG.normal(900,250),300,2000))
    if seg=="Heavy Daily":     return float(np.clip(RNG.normal(2700,600),1200,5000))
    return float(np.clip(RNG.normal(1500,400),700,3000))  # Weekend Warrior
def severity(seg):  # multiplier mempercepat degradasi oli (medan berat/macet/beban)
    if seg=="Heavy Daily":     return float(np.clip(RNG.normal(1.20,0.08),1.0,1.5))
    if seg=="Weekend Warrior": return float(np.clip(RNG.normal(1.30,0.12),1.0,1.7))
    return float(np.clip(RNG.normal(1.02,0.05),0.9,1.2))

# ----------------------------------------------------------------------------
# 4. KATALOG ITEM SERVIS + HARGA (IDR) untuk market basket & revenue
# ----------------------------------------------------------------------------
def harga_acak(lo,hi): return int(round(RNG.integers(lo,hi)/1000)*1000)
ITEM_PRICE = {
    "Filter Oli":            (60000,120000),
    "Filter Udara":          (120000,260000),
    "Filter Kabin/AC":       (90000,190000),
    "Busi (set)":            (200000,460000),
    "Tune Up / Servis Berkala":(350000,720000),
    "Kampas Rem Depan":      (400000,820000),
    "Kampas Rem Belakang":   (380000,760000),
    "Oli Gardan/Transfer":   (250000,460000),
    "Coolant/Radiator":      (120000,260000),
    "Aki/Accu":              (900000,1850000),
    "Wiper":                 (90000,210000),
    "Servis AC":             (250000,600000),
    "Spooring & Balancing":  (250000,450000),
    "Ban (per pcs)":         (650000,1400000),
}

# ----------------------------------------------------------------------------
# 5. GENERATE CUSTOMERS & CARS
# ----------------------------------------------------------------------------
cust_rows, car_rows = [], []
# sebagian pemilik punya >1 mobil
n_owners = int(N_CARS*0.86)
owners = []
for i in range(n_owners):
    owners.append({
        "customer_id": f"CUST{i+1:04d}",
        "nama_pemilik": buat_nama(),
        "no_telepon": buat_hp(),
        "alamat": buat_alamat(),
    })
    kec,pos = KECAMATAN[RNG.integers(len(KECAMATAN))]
    owners[-1]["kecamatan"]=kec; owners[-1]["kode_pos"]=pos; owners[-1]["kota"]="Medan"

car_id = 0
for c in range(N_CARS):
    owner = owners[c] if c < n_owners else owners[RNG.integers(n_owners)]  # multi-mobil
    idx = RNG.choice(len(cat_df), p=cat_w)
    m = cat_df.iloc[idx]
    seg = SEGMEN[RNG.choice(3,p=SEG_P)]
    tahun = int(RNG.integers(2016,2026))
    # transmisi
    t = TRANSMISI_BY_MODEL.get(m["model"],"AT")
    transmisi = RNG.choice(t.split("/")) if "/" in t else t
    car_id += 1
    car_rows.append({
        "car_id": f"CAR{car_id:04d}",
        "customer_id": owner["customer_id"],
        "nopol": buat_nopol(),
        "model": m["model"], "varian": m["varian"], "tahun": tahun,
        "bahan_bakar": m["bahan_bakar"], "penggerak": m["penggerak"],
        "transmisi": transmisi, "jenis_oli": m["jenis_oli"],
        "harga_oli_jasa": int(m["harga_oli"]),
        "interval_oli_km": oil_interval_km(m["bahan_bakar"], m["jenis_oli"]),
        "segmen_pemakaian_asli": seg,
        "km_per_bulan": round(km_per_bulan(seg),1),
        "severity": round(severity(seg),3),
    })
cars = pd.DataFrame(car_rows)
cust = pd.DataFrame(owners)

# ----------------------------------------------------------------------------
# 6. SEASONALITY HELPERS (untuk demand forecast)
# ----------------------------------------------------------------------------
LEBARAN = [date(2022,5,2), date(2023,4,22), date(2024,4,10), date(2025,3,31), date(2026,3,20)]
LIBUR = set()  # beberapa libur nasional utama (bengkel sepi/tutup)
for y in range(2022,2027):
    for md in [(1,1),(8,17),(12,25),(6,1)]:
        LIBUR.add(date(y,md[0],md[1]))
for l in LEBARAN:
    for d in range(-2,4): LIBUR.add(l+timedelta(days=d))  # cuti bersama

def dow_weight(d):                       # Sabtu ramai, Minggu sepi
    return {0:1.0,1:1.0,2:1.05,3:1.05,4:1.15,5:1.45,6:0.35}[d.weekday()]
def payday_weight(d):                    # pasca-gajian tgl 25-5
    return 1.25 if (d.day>=25 or d.day<=5) else 1.0
def lebaran_weight(d):                   # surge mudik 3 minggu sebelum Lebaran
    for l in LEBARAN:
        delta=(l-d).days
        if 0 < delta <= 21: return 1.0 + 0.9*(1-delta/21)
    return 1.0
def season_mult(d):
    if d in LIBUR: return 0.15
    return dow_weight(d)*payday_weight(d)*lebaran_weight(d)

def geser_tanggal(due):                  # geser ke hari realistis dekat due date via accept-reject
    for _ in range(40):
        cand = due + timedelta(days=int(RNG.integers(-6,7)))
        if cand < WINDOW_START or cand > WINDOW_END: continue
        if RNG.random() < season_mult(cand)/1.6:
            return cand
    return min(max(due,WINDOW_START),WINDOW_END)

# ----------------------------------------------------------------------------
# 7. GENERATE RIWAYAT SERVIS (per mobil: rangkaian ganti oli + item menumpang)
# ----------------------------------------------------------------------------
svc_rows=[]; visit_id=0; service_id=0
CABANG = ["Cabang Gatot Subroto","Cabang Sisingamangaraja","Cabang Ringroad",
          "Cabang Krakatau","Cabang Setia Budi"]
MEKANIK = [f"Mekanik {n}" for n in ["Anto","Rudi","Sahat","Joni","Beni","Dani","Hasan","Tigor"]]

def tambah_item(visit_ctx, item, qty=1):
    global service_id
    service_id+=1
    lo,hi = ITEM_PRICE.get(item,(0,0))
    if item=="__OLI__":
        nama="Ganti Oli Mesin"; kategori="Oli & Filter"
        harga=visit_ctx["harga_oli"]
    else:
        nama=item; harga=harga_acak(lo,hi)
        kategori=("Oli & Filter" if "Filter" in item else
                  "Tune Up" if "Tune" in item or "Busi" in item else
                  "Rem & Kaki" if ("Rem" in item or "Ban" in item or "Spooring" in item) else
                  "Drivetrain" if "Gardan" in item else
                  "Pendingin" if ("Coolant" in item or "AC" in item) else
                  "Kelistrikan" if "Aki" in item else "Lainnya")
    svc_rows.append({
        "service_id": f"SVC{service_id:06d}", "visit_id": visit_ctx["vid"],
        "car_id": visit_ctx["car_id"], "tanggal": visit_ctx["tgl"].isoformat(),
        "km_saat_servis": visit_ctx["km"], "cabang": visit_ctx["cabang"],
        "mekanik": visit_ctx["mekanik"], "kategori_servis": kategori,
        "item_servis": nama, "qty": qty, "harga": harga,
    })

for _, car in cars.iterrows():
    seg=car["segmen_pemakaian_asli"]; kmpb=car["km_per_bulan"]; sev=car["severity"]
    interval_km=car["interval_oli_km"]; fuel=car["bahan_bakar"]; drive=car["penggerak"]
    # mulai tracking: km awal & tanggal masuk pertama
    km = int(RNG.integers(2000, 60000))
    # tanggal servis pertama acak dalam paruh pertama window
    t0 = WINDOW_START + timedelta(days=int(RNG.integers(0, 540)))
    km_since_busi=int(RNG.integers(0,30000)); km_since_brake=int(RNG.integers(0,40000))
    km_since_gardan=int(RNG.integers(0,30000)); last_aki = t0 - timedelta(days=int(RNG.integers(0,900)))
    cab = RNG.choice(CABANG)  # pelanggan cenderung setia 1 cabang
    cur = t0
    while cur <= WINDOW_END:
        # interval waktu efektif = interval_km/severity dibagi km per hari
        eff_km = interval_km / sev
        # kepatuhan: sebagian telat (lognormal sekitar 1.05)
        patuh = float(np.clip(RNG.lognormal(0.03,0.18),0.7,1.8))
        eff_km *= patuh
        hari = eff_km / max(kmpb/30.0, 1.0)
        hari = float(np.clip(hari, 25, 380))        # cap kalender ~ <13 bln
        cur = cur + timedelta(days=int(round(hari)))
        if cur > WINDOW_END: break
        tgl = geser_tanggal(cur)
        km += int(round((tgl-(tgl-timedelta(days=int(round(hari)))) ).days * kmpb/30.0))
        km_since_busi += int(eff_km); km_since_brake += int(eff_km); km_since_gardan += int(eff_km)
        visit_id+=1
        vctx={"vid":f"V{visit_id:06d}","car_id":car["car_id"],"tgl":tgl,"km":int(km),
              "cabang":cab,"mekanik":RNG.choice(MEKANIK),"harga_oli":int(car["harga_oli_jasa"])}
        # --- item inti: oli mesin (selalu) ---
        tambah_item(vctx,"__OLI__")
        # --- struktur asosiasi (dibangun sengaja) ---
        if RNG.random()<0.85: tambah_item(vctx,"Filter Oli")        # rule kuat oli->filter oli
        if RNG.random()<0.42 or km_since_busi>=18000:
            tambah_item(vctx,"Filter Udara")
        if RNG.random()<0.30: tambah_item(vctx,"Filter Kabin/AC")
        # busi: hanya bensin/hybrid, pada milestone km
        if fuel in ("Bensin","Hybrid") and km_since_busi>=30000 and RNG.random()<0.7:
            tambah_item(vctx,"Busi (set)"); km_since_busi=0
        # tune up cenderung di milestone (kelipatan ~20k)
        if RNG.random()< (0.45 if (km%20000)<3000 else 0.18):
            tambah_item(vctx,"Tune Up / Servis Berkala")
        # rem
        if km_since_brake>=35000 and RNG.random()<0.6:
            tambah_item(vctx,"Kampas Rem Depan")
            if RNG.random()<0.45: tambah_item(vctx,"Kampas Rem Belakang")
            km_since_brake=0
        # oli gardan/transfer: khusus 4x4 / RWD pada milestone
        if drive in ("4x4","RWD") and km_since_gardan>=40000 and RNG.random()<0.55:
            tambah_item(vctx,"Oli Gardan/Transfer"); km_since_gardan=0
        # coolant occasional
        if RNG.random()<0.12: tambah_item(vctx,"Coolant/Radiator")
        # aki ~tiap 2.5 th
        if (tgl-last_aki).days>900 and RNG.random()<0.5:
            tambah_item(vctx,"Aki/Accu"); last_aki=tgl
        if RNG.random()<0.10: tambah_item(vctx,"Wiper")

# --- kunjungan non-oli (biar basket tidak trivial: oli selalu ada) ---
n_nonoil = int(visit_id*0.18)
for _ in range(n_nonoil):
    car = cars.iloc[RNG.integers(len(cars))]
    tgl = geser_tanggal(WINDOW_START+timedelta(days=int(RNG.integers(60, (WINDOW_END-WINDOW_START).days))))
    visit_id+=1
    vctx={"vid":f"V{visit_id:06d}","car_id":car["car_id"],"tgl":tgl,
          "km":int(RNG.integers(20000,180000)),"cabang":RNG.choice(CABANG),
          "mekanik":RNG.choice(MEKANIK),"harga_oli":0}
    pick = RNG.choice(["Servis AC","Kampas Rem Depan","Aki/Accu","Spooring & Balancing",
                       "Ban (per pcs)","Busi (set)","Coolant/Radiator"])
    tambah_item(vctx,pick, qty=(4 if pick=="Ban (per pcs)" else 1))
    if pick=="Servis AC" and RNG.random()<0.5: tambah_item(vctx,"Filter Kabin/AC")
    if pick=="Kampas Rem Depan" and RNG.random()<0.4: tambah_item(vctx,"Kampas Rem Belakang")
    if pick=="Spooring & Balancing" and RNG.random()<0.5: tambah_item(vctx,"Ban (per pcs)",qty=2)

svc = pd.DataFrame(svc_rows).sort_values("tanggal").reset_index(drop=True)

# ----------------------------------------------------------------------------
# 8. SIMPAN + VERIFIKASI
# ----------------------------------------------------------------------------
cars_out = cars.merge(cust, on="customer_id", how="left")
# urutan kolom master
cust_cols = ["customer_id","nama_pemilik","no_telepon","alamat","kecamatan","kota","kode_pos",
    "car_id","nopol","model","varian","tahun","bahan_bakar","penggerak","transmisi",
    "jenis_oli","interval_oli_km","segmen_pemakaian_asli","km_per_bulan"]
cars_out = cars_out[cust_cols]

cust.to_csv("/home/claude/pelanggan.csv", index=False)
cars_out.to_csv("/home/claude/pelanggan_mobil.csv", index=False)
svc.to_csv("/home/claude/riwayat_servis.csv", index=False)

print("=== RINGKASAN DATASET ===")
print(f"Pelanggan unik   : {cust.shape[0]}")
print(f"Mobil unik       : {cars.shape[0]}")
print(f"Kunjungan (visit): {svc['visit_id'].nunique()}")
print(f"Baris item servis: {svc.shape[0]}  <-- ini 'row data' utama")
print(f"Rentang tanggal  : {svc['tanggal'].min()} s/d {svc['tanggal'].max()}")
print(f"Total revenue     : Rp {svc['harga'].sum():,.0f}")
print("\n--- Distribusi segmen (ground truth) ---")
print(cars['segmen_pemakaian_asli'].value_counts())
print("\n--- Top 10 item servis ---")
print(svc['item_servis'].value_counts().head(10))
print("\n--- Cek sinyal SURVIVAL: rata-rata interval oli (hari) per segmen ---")
tmp = svc[svc['item_servis']=="Ganti Oli Mesin"].merge(cars[['car_id','segmen_pemakaian_asli']],on='car_id')
tmp['tanggal']=pd.to_datetime(tmp['tanggal'])
tmp=tmp.sort_values(['car_id','tanggal'])
tmp['gap']=tmp.groupby('car_id')['tanggal'].diff().dt.days
print(tmp.groupby('segmen_pemakaian_asli')['gap'].mean().round(1))
print("\n--- Cek sinyal BASKET: P(item | visit ada Ganti Oli) ---")
oil_visits=set(svc[svc['item_servis']=="Ganti Oli Mesin"]['visit_id'])
sub=svc[svc['visit_id'].isin(oil_visits)]
n=len(oil_visits)
for it in ["Filter Oli","Filter Udara","Busi (set)","Tune Up / Servis Berkala"]:
    p=sub[sub['item_servis']==it]['visit_id'].nunique()/n
    print(f"  P({it:<28}| oli) = {p:.2f}")
