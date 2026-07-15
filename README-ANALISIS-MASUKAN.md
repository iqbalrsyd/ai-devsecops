# Analisis Masukan Dosen Pembimbing terhadap Bab I–IV

## Verdict Umum: Masukan ini **CUKUP** — tidak kurang, tidak berlebihan

Masukan yang diberikan dosbing ini berada pada kualitas dan kedalaman yang sangat baik. Ia tidak sekadar memberi kritik permukaan, tetapi membongkar struktur argumentasi dan menyarankan perbaikan yang bersifat fundamental. Namun ada beberapa poin yang menurut saya bisa diperhalus bobotnya, dan ada beberapa yang memang wajib diikuti. Berikut analisis per-bab.

---

## 1. Masukan terhadap Bab I — **CUKUP, bahkan sangat tajam**

### Ringkasan masukan dosbing:
- Alur argumentasi ilmiahmu masih lemah: dari "variasi repo → generic pipeline → LLM → proposed system", seharusnya "variasi repo → attack surface berbeda → security requirement berbeda → generic pipeline gagal → LLM reasoning → proposed system".
- Novelty bukan "AI bikin pipeline", tetapi "_security requirement berbeda karena attack surface berbeda_". AI hanya alat inferensi.

### Analisis saya:
**Masukan ini sangat tepat dan fundamental.** Ini bukan soal kosmetik penulisan, melainkan soal fondasi logika penelitian. Jika alur argumentasi di Bab I tidak diperbaiki seperti yang disarankan, penguji bisa dengan mudah mematahkan klaim kontribusimu.

Rantai kausal yang disarankan dosbing (`attack surface berbeda → security requirement berbeda → generic pipeline gagal`) membangun narasi kenapa penelitian ini _harus ada_. Tanpa itu, pembaca akan bertanya: "Memangnya kenapa kalau repo berbeda-beda? Kan bisa pakai pipeline yang sama?"

**Verdict: WAJIB dilakukan. Masukan ini cukup (pas).**

---

## 2. Masukan terhadap Bab II — **CUKUP, sangat presisi**

### Ringkasan masukan dosbing:
- Struktur Bab II (penelitian terdahulu → teori → analisis metode → RQ) sudah bagus.
- Tabel penelitian terdahulu terlalu sederhana (Ya/Tidak/Sebagian). Harus ada justifikasi kenapa suatu paper dinilai "Tidak" atau "Sebagian".

### Analisis saya:
Ini masukan yang sering diabaikan mahasiswa tapi sangat krusial. Tabel perbandingan tanpa justifikasi adalah lubang besar saat sidang. Penguji tinggal tanya satu paper: "Kenapa Anda bilang paper ini tidak melakukan _repository analysis_?" — dan kamu tidak bisa menjawab.

Dosbing memberi contoh konkret:
```
Paper A → hanya membaca dependency → tidak membaca deployment → tidak membaca architecture → Partial
```

**Verdict: WAJIB dilakukan. Masukan ini cukup (pas).**

---

## 3. Masukan terhadap Bab III — **CUKUP, tapi agak ketat**

### Ringkasan masukan dosbing:
- Bab III terlalu implementatif (banyak _node_, _prompt_, _workflow_, JSON, YAML).
- Metode penelitian harus menjawab "bagaimana eksperimen dilakukan", bukan "bagaimana coding dilakukan".
- Sarannya: pindahkan sebagian besar ke Bab IV. Bab III cukup jelaskan Input → Proses → Output per tahap.

### Analisis saya:
Secara filosofis, dosbing **benar** — Bab III adalah metode penelitian, bukan dokumentasi teknis. Namun, untuk penelitian berbasis AI/LLM seperti milikmu, batas antara "metode" dan "implementasi" tidak sepenuhnya hitam-putih.

**Saran praktis saya:**
- Jangan pindahkan _semua_ detail implementasi ke Bab IV, karena prompt engineering dan workflow LLM adalah bagian dari metodemu (bukan sekadar implementasi).
- Pindahkan detail yang bersifat engineering murni (response formatter, job reasoning sebagai kode) ke Bab IV.
- Pertahankan arsitektur prompt dan logika inferensi di Bab III sebagai bagian dari desain eksperimen.
- Gunakan diagram alir Input → Proses → Output yang dosbing sarankan **sebagai pembuka setiap tahap**, lalu beri narasi singkat.

**Verdict: Sebagian besar WAJIB, tapi tidak perlu seekstrem yang disarankan. Masukan ini agak ketat tapi tetap _cukup_.**

---

## 4. Masukan terhadap Bab IV — **SEDIKIT BERLEBIHAN dalam ekspektasi, tapi arahnya BENAR**

### Ringkasan masukan dosbing:
- Struktur Bab IV sekarang campur aduk antara "hasil penelitian" dan "manual implementasi".
- Bab IV seharusnya menjawab RQ, bukan menjadi dokumentasi software.
- Menyarankan restrukturisasi total menjadi: 4.1 Experimental Setup, 4.2–4.4 Menjawab RQ1, 4.5–4.6 Menjawab RQ2, 4.7 Perbandingan dengan penelitian terdahulu, 4.8 Diskusi Menjawab RQ.

### Analisis saya:
**Arahnya 100% benar.** Bab IV memang harus membuktikan hipotesis, bukan mendokumentasikan fitur. Tapi saya merasa ada sedikit **over-expectation** dari dosbing pada beberapa poin:

#### Yang wajib dilakukan:
1. **Restrukturisasi Bab IV mengikuti template menjawab RQ.** Ini non-negotiable.
2. **Menambahkan perbandingan dengan penelitian terdahulu secara eksplisit.** Kalau kamu klaim "lebih baik", Bab IV harus membuktikan dengan data.
3. **Diskusi Menjawab RQ di akhir Bab IV.** Ini memberi penutup naratif yang kuat.

#### Yang mungkin berlebihan:
1. **"Jangan ada dokumentasi software sama sekali."** Untuk skripsi S1 berbasis rekayasa perangkat lunak, dokumentasi sistem (API, database, frontend) masih dibutuhkan sebagai bukti bahwa sistem benar-benar dibangun. Solusinya: letakkan di **lampiran** atau di subbab terpisah yang jelas diberi label sebagai "Implementasi Sistem" — bukan sebagai bagian dari hasil penelitian.
2. **Ekspektasi ground truth vs prediction untuk setiap aspek repository.** Ini ideal secara akademik, tapi membangun ground truth untuk 4+ repositori dengan 4 dimensi analisis (bahasa, arsitektur, deployment, kategori) membutuhkan effort validasi manual yang sangat besar. Jika waktunya tidak cukup, gunakan sampel yang representatif (misal 2 repositori dengan ground truth lengkap, sisanya divalidasi secara kualitatif).

**Verdict: Arah BENAR, tapi beberapa ekspektasi bisa dinegosiasikan. Masukan ini _cukup_ secara kualitas, tapi agak tinggi untuk skala S1.**

---

## 5. Masukan tentang Validasi Penelitian Terdahulu — **CUKUP, sangat elegan**

Dosbing menyarankan agar tidak bilang "paper lama kurang bagus", tetapi jelaskan bahwa "paper tersebut valid, tetapi scope-nya berbeda". Ini sangat elegan secara akademik dan menghindari konfrontasi yang tidak perlu. **WAJIB diikuti.**

---

## Tabel Ringkasan

| Aspek | Verdict | Prioritas |
|-------|---------|-----------|
| Alur argumentasi Bab I | Cukup, wajib | **HIGH** |
| Tabel justifikasi Bab II | Cukup, wajib | **HIGH** |
| Bab III terlalu implementatif | Cukup, sebagian wajib | **MEDIUM** |
| Restrukturisasi Bab IV jadi menjawab RQ | Cukup, wajib | **HIGH** |
| Perbandingan dengan penelitian terdahulu | Cukup, wajib | **HIGH** |
| Diskusi Menjawab RQ | Cukup, wajib | **HIGH** |
| Nol dokumentasi software | Agak berlebihan | **LOW** |
| Validasi penelitian terdahulu | Cukup, wajib | **MEDIUM** |
| Ground truth untuk semua repo | Agak berlebihan | **MEDIUM** |

---

## Saran Tambahan dari Saya (yang tidak disebut dosbing)

1. **Tambahkan "Threats to Validity"** di Bab IV atau Bab VI. Ini standar di paper security dan menunjukkan kamu sadar akan keterbatasan penelitianmu sendiri. Penguji akan menghargai ini.

2. **Perjelas metrik evaluasi sejak Bab III.** Dosbing menyebut Precision, Recall, Coverage Accuracy, CVSS, Security Coverage Score — tapi tidak menyebutkan bahwa metrik ini harus didefinisikan di Bab III sebagai bagian dari desain eksperimen. Jangan sampai metrik baru muncul pertama kali di Bab IV.

3. **Pertimbangkan menambah satu repositori kontrol** — repositori yang sengaja tidak memiliki kerentanan — untuk menguji false positive rate dari pipeline-mu. Ini akan sangat memperkuat klaim bahwa pipeline-mu "adaptive" dan bukan sekadar "menembak semua kontrol keamanan".

4. **Sinkronkan istilah antar bab.** Saat ini dosbing mencatat adanya inkonsistensi antara istilah di Bab I, II, III, dan IV. Sebelum revisi, buat daftar istilah kunci dan pastikan konsisten di seluruh bab.

---

## Kesimpulan

Masukan dosbing ini **CUKUP secara kuantitas dan kualitas**. Tidak ada yang perlu ditambah (ia sudah mencakup semua bab dan semua dimensi kritik), dan hanya ada beberapa ekspektasi yang bisa dinegosiasikan (dokumentasi software dan skala ground truth). Jika kamu mengikuti 80% dari masukan ini, kualitas skripsimu akan naik signifikan dan kamu akan jauh lebih siap menghadapi sidang.
