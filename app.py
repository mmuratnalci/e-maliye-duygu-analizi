import io
import re
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Vatandaş Yorumları Duygu Analizi",
    page_icon="💬",
    layout="wide",
)

OLUMLU = "Olumlu"
OLUMSUZ = "Olumsuz"
NOTR = "Nötr"
RENKLER = {OLUMLU: "#2E9E6B", OLUMSUZ: "#D64545", NOTR: "#8A94A6"}

# Kökler ön ek eşleşmesiyle aranır (ör. "memnun" -> "memnunum", "memnuniyet").
OLUMLU_KOKLER = [
    "iyi", "güzel", "harika", "mükemmel", "memnun", "teşekkür", "sağol", "tebrik",
    "başarılı", "hızlı", "kolay", "pratik", "kullanışlı", "faydalı", "yararlı",
    "kaliteli", "profesyonel", "ilgili", "yardımcı", "çözüm", "çözül", "rahat",
    "net", "anlaşılır", "sorunsuz", "güvenilir", "süper", "muhteşem", "beğen",
    "sevdi", "sevi", "takdir", "hoş", "verimli", "etkili", "pratik", "kusursuz",
    "tavsiye", "önerir", "mutlu", "sevindi", "olumlu", "gelişti", "iyileş",
    "kolaylık", "zahmetsiz", "tamam", "sağlam", "şahane", "bravo", "eyvallah",
]
OLUMSUZ_KOKLER = [
    "kötü", "berbat", "rezalet", "yetersiz", "yavaş", "sorun", "problem", "şikayet",
    "şikâyet", "mağdur", "memnuniyetsiz", "karmaşık", "zor", "çöktü", "çöküyor",
    "hata", "arıza", "bozuk", "donuyor", "açılmıyor", "gecik", "bekle", "perişan",
    "saçma", "vasat", "ilgisiz", "kaba", "adaletsiz", "haksız", "yanlış", "eksik",
    "pahalı", "rezil", "felaket", "çile", "sıkıntı", "kızgın", "sinir", "bıktı",
    "usandı", "mağduriyet", "cevapsız", "ulaşılamıyor", "ulaşamıyor", "belirsiz",
    "gereksiz", "işe yaramaz", "korkunç", "utanç", "tepki", "yetmiyor", "çözülmü",
    "hayal kırıklığı", "dolandır", "kayıp", "ceza", "hantal", "kasıyor",
]
# Bu kökler olumlu kökle çakışsa bile olumsuz sayılır (ör. "memnuniyetsiz").
OLUMSUZ_ONCELIKLI = ("memnuniyetsiz", "çözülmü")

OLUMSUZLAMA_KELIMELERI = {
    "değil", "degil", "yok", "yoktur", "asla", "hiçbir", "hiçbiri", "olmaz", "olmuyor",
}
# Fiil olumsuzlama ekleri: kalmadım, olmadı, yapmaz, çalışmıyor, çözmeyen...
OLUMSUZ_EK = re.compile(
    r"(m[ae]d[ıiuü]|m[ae]z|m[ae]y[ae]cak|m[ıiuü]yor|m[ae]yan|m[ae]m[ae]k)"
)
PENCERE = 3

DURAK_KELIMELER = set(
    """
    ve veya ile ama fakat ancak çünkü için gibi kadar daha çok az bir bu şu o bunu şunu
    onu bunlar şunlar onlar ben sen biz siz ben benim bizim sizin onun bunun da de ki mi mı
    mu mü ne neden nasıl her hiç hiçbir bazı tüm bütün olarak olan olarak oldu olur olmuş
    var yok ise ya yani hem en ise sonra önce kez defa gün şey şeyler ayrıca zaten bile
    ile ise bana beni bize bizi size sizi ona ondan bundan şundan burada orada şimdi hala
    hâlâ artık sadece yalnızca ancak üzerinde üzerine içinde arasında göre rağmen dolayı
    kadar diye ben değil bende sende biraz bence sanki eğer şayet olsa olsun etti ediyor
    edildi edilen etmek yapmak yaptı yapıyor yapılan yapıldı yaptım gerek gerekiyor
    lütfen merhaba selam iyi günler sayın evet hayır ise mı mi
    """.split()
)

ENCODINGS = ["utf-8-sig", "utf-8", "cp1254", "iso-8859-9", "utf-16", "cp1252", "latin-1"]


def tr_kucult(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").lower()


def tokenla(metin: str) -> list[str]:
    return re.findall(r"[a-zçğıöşüâîû]+", tr_kucult(metin))


def _kok_eslesir(token: str, kok: str) -> bool:
    return token.startswith(kok)


def _olumsuzlandi(tokenlar: list[str], i: int, kok_uzunlugu: int) -> bool:
    # Duygu sözcüğünün kendi ekinde olumsuzlama (ör. "beğenmedim").
    kalan = tokenlar[i][kok_uzunlugu:]
    if kalan and OLUMSUZ_EK.search(kalan):
        return True
    for t in tokenlar[i + 1 : i + 1 + PENCERE]:
        if t in OLUMSUZLAMA_KELIMELERI or OLUMSUZ_EK.search(t):
            return True
    # Önceki sözcük "hiç/asla" gibi bir olumsuzlayıcıysa.
    return i > 0 and tokenlar[i - 1] in {"asla", "hiç", "hiçbir", "değil"}


def duygu_puani(metin) -> tuple[int, str]:
    if not isinstance(metin, str) or not metin.strip():
        return 0, "Boş"
    tokenlar = tokenla(metin)
    puan = 0
    for i, t in enumerate(tokenlar):
        kok = next((k for k in OLUMSUZ_ONCELIKLI if t.startswith(k)), None)
        yon = -1 if kok else 0
        if not kok:
            kok = next((k for k in OLUMLU_KOKLER if _kok_eslesir(t, k)), None)
            if kok:
                yon = 1
            else:
                kok = next((k for k in OLUMSUZ_KOKLER if _kok_eslesir(t, k)), None)
                if kok:
                    yon = -1
        if not kok:
            continue
        # "memnuniyetsiz" gibi -siz ekli sözcükler olumsuz kök olarak zaten sayılır.
        if _olumsuzlandi(tokenlar, i, len(kok)):
            yon = -yon
        puan += yon
    if puan > 0:
        return puan, OLUMLU
    if puan < 0:
        return puan, OLUMSUZ
    return 0, NOTR


def en_sik_kelimeler(metinler, n=15) -> pd.DataFrame:
    sayac = Counter()
    for m in metinler:
        if isinstance(m, str):
            sayac.update(
                t for t in tokenla(m) if len(t) > 2 and t not in DURAK_KELIMELER
            )
    return pd.DataFrame(sayac.most_common(n), columns=["Kelime", "Sıklık"])


@st.cache_data(show_spinner=False)
def dosya_oku(veri: bytes, ad: str) -> pd.DataFrame:
    if ad.lower().endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(veri), engine="openpyxl")
    son_hata = None
    for kodlama in ENCODINGS:
        try:
            metin = veri.decode(kodlama)
        except (UnicodeDecodeError, UnicodeError) as e:
            son_hata = e
            continue
        try:
            return pd.read_csv(io.StringIO(metin), sep=None, engine="python")
        except Exception as e:  # ayraç tespiti başarısızsa virgül dene
            son_hata = e
            try:
                return pd.read_csv(io.StringIO(metin))
            except Exception as e2:
                son_hata = e2
    raise ValueError(f"CSV dosyası okunamadı: {son_hata}")


@st.cache_data(show_spinner=False)
def analiz_et(yorumlar: tuple) -> pd.DataFrame:
    sonuc = [duygu_puani(y) for y in yorumlar]
    return pd.DataFrame(
        {"Duygu Puanı": [s[0] for s in sonuc], "Duygu": [s[1] for s in sonuc]}
    )


st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 1200px;}
    .baslik {font-size: 2.2rem; font-weight: 700; margin-bottom: 0;}
    .alt-baslik {color: #6b7280; margin-bottom: 1.2rem;}
    </style>
    <p class="baslik">💬 Vatandaş Yorumları Duygu Analizi</p>
    <p class="alt-baslik">Yorum dosyanızı yükleyin; olumlu, olumsuz ve nötr dağılımını görün.</p>
    """,
    unsafe_allow_html=True,
)

st.info(
    "⚠️ Bu analiz **kural tabanlı** çalışır: Türkçe olumlu/olumsuz sözcük listeleri ve "
    "olumsuzlama ifadeleri kullanılır. İroni, deyimler ve bağlam anlaşılamaz; "
    "sonuçlar **hata içerebilir**. Önemli kararlarda yorumları ayrıca elle kontrol edin."
)

with st.sidebar:
    st.header("📁 Veri Yükleme")
    dosya = st.file_uploader("CSV veya Excel (.xlsx) dosyası", type=["csv", "xlsx"])
    st.caption("CSV: UTF-8, Windows-1254 ve ISO-8859-9 kodlamaları desteklenir.")

if dosya is None:
    st.write("Başlamak için sol taraftan bir dosya yükleyin.")
    st.stop()

try:
    df = dosya_oku(dosya.getvalue(), dosya.name)
except Exception as e:
    st.error(f"Dosya okunamadı: {e}")
    st.stop()

if df.empty or df.shape[1] == 0:
    st.warning("Yüklenen dosyada veri bulunamadı.")
    st.stop()

df.columns = [str(c) for c in df.columns]

st.subheader("Veri Önizleme")
st.caption(f"Toplam {len(df)} satır, {df.shape[1]} sütun. İlk 10 satır:")
st.dataframe(df.head(10), use_container_width=True)

varsayilan = next(
    (i for i, c in enumerate(df.columns) if re.search(r"yorum|görüş|mesaj|metin|comment", tr_kucult(c))),
    0,
)
sutun = st.selectbox("Analiz edilecek yorum sütunu", list(df.columns), index=varsayilan)

if not st.button("Analiz Et", type="primary"):
    st.stop()

sonuc_df = df.copy()
yorumlar = sonuc_df[sutun].where(sonuc_df[sutun].notna(), None)
yorumlar = yorumlar.map(lambda x: x if x is None else str(x))
analiz = analiz_et(tuple(yorumlar))
sonuc_df["Duygu Puanı"] = analiz["Duygu Puanı"].values
sonuc_df["Duygu"] = analiz["Duygu"].values

bos_sayi = int((sonuc_df["Duygu"] == "Boş").sum())
gecerli = sonuc_df[sonuc_df["Duygu"] != "Boş"]

if bos_sayi:
    st.warning(f"{bos_sayi} boş yorum analiz dışı bırakıldı.")
if gecerli.empty:
    st.error("Seçilen sütunda analiz edilebilecek yorum bulunamadı.")
    st.stop()

sayilar = (
    gecerli["Duygu"].value_counts().reindex([OLUMLU, OLUMSUZ, NOTR], fill_value=0)
)
dagilim = sayilar.rename_axis("Duygu").reset_index(name="Yorum Sayısı")

st.subheader("Sonuç Özeti")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Analiz edilen", len(gecerli))
c2.metric("Olumlu", int(sayilar[OLUMLU]))
c3.metric("Olumsuz", int(sayilar[OLUMSUZ]))
c4.metric("Nötr", int(sayilar[NOTR]))

st.subheader("Duygu Dağılımı")
g1, g2 = st.columns(2)
with g1:
    fig = px.pie(
        dagilim, names="Duygu", values="Yorum Sayısı", color="Duygu",
        color_discrete_map=RENKLER, hole=0.45,
    )
    fig.update_layout(margin=dict(t=20, b=20), legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)
with g2:
    fig = px.bar(
        dagilim, x="Duygu", y="Yorum Sayısı", color="Duygu",
        color_discrete_map=RENKLER, text="Yorum Sayısı",
    )
    fig.update_layout(margin=dict(t=20, b=20), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.subheader("En Sık Kullanılan 15 Anlamlı Kelime")
kelimeler = en_sik_kelimeler(gecerli[sutun])
if kelimeler.empty:
    st.info("Gösterilecek anlamlı kelime bulunamadı.")
else:
    fig = px.bar(
        kelimeler.sort_values("Sıklık"), x="Sıklık", y="Kelime",
        orientation="h", text="Sıklık", color_discrete_sequence=["#3B6FD4"],
    )
    fig.update_layout(margin=dict(t=20, b=20), height=480)
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Olumsuz Yorumlar")
olumsuz = gecerli[gecerli["Duygu"] == OLUMSUZ].sort_values("Duygu Puanı")
if olumsuz.empty:
    st.success("Olumsuz olarak sınıflandırılan yorum bulunamadı.")
else:
    st.caption(f"{len(olumsuz)} olumsuz yorum (en olumsuzdan başlayarak).")
    st.dataframe(olumsuz, use_container_width=True)

st.subheader("Sonuçları İndir")
csv_baytlari = sonuc_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇️ Sonuçları CSV olarak indir",
    data=csv_baytlari,
    file_name="duygu_analizi_sonuclari.csv",
    mime="text/csv",
)
