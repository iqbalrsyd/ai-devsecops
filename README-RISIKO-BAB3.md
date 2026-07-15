# Risiko Terbesar Bab III (Perspektif Penguji)

Dari semua isi Bab III, ini 5 risiko yang paling bisa bikin kamu dipatahkan saat sidang:

---

## Risiko #1 — Prompt Engineering Bukan Metode Penelitian

**Ini yang paling riskan.**

Sekarang Bab III banyak menjelaskan prompt LLM mentah-mentah (teks panjang, format JSON, instruksi ke AI). Penguji bisa bilang:

> "Anda menulis prompt, bukan metode penelitian. Apa bedanya ini dengan dokumentasi API ChatGPT?"

**Kenapa riskan:**
- Prompt adalah **cara kamu mengoperasikan tools**, bukan **metode ilmiah**.
- Kalau kamu ganti model LLM (dari GPT-4o ke Claude), prompt harus berubah — artinya prompt bukanlah konstanta metodologis.
- Penguji bisa tanya: "Apakah prompt ini divalidasi? Siapa yang menyusun? Atas dasar apa?"

**Cara perbaiki:**
- Jangan tulis prompt lengkap. Tulis **struktur prompt**: apa yang dimasukkan (konteks repo, library, entity, route), apa format outputnya (JSON skema), apa constraint-nya (hanya 3 domain, confidence threshold).
- Pindahkan prompt lengkap ke **Lampiran**.
- Jelaskan di Bab III bahwa prompt disusun dengan pendekatan **few-shot structured prompting** yang divalidasi melalui uji coba pada repositori sampel.

---

## Risiko #2 — Tidak Bisa Bedakan Metode vs Implementasi

**Ini inti kritik dosbingmu.**

Di codebase, `domain_detection_node.py` (653 baris), `workflow_generator.py` (6947 baris), `job_reasoning_node.py` (1208 baris) — ini semua adalah kode. Tapi Bab III menjelaskan kode sebagai metode.

**Kenapa riskan:**
- Penguji teknik informatika akan bedakan dengan jelas: mana _how the system works_ (Bab IV) dan mana _why it's designed that way_ (Bab III).
- Kalau Bab III isinya "node ini memanggil fungsi X, membaca state Y, return Z" — itu dokumentasi software.

**Cara perbaiki:**
- Untuk setiap node, jelaskan **keputusan desain**-nya, bukan **eksekusi kode**-nya.
  - Kenapa pakai LLM di node ini dan bukan di node lain?
  - Kenapa pakai threshold 0.50 untuk domain confidence?
  - Kenapa deterministic untuk workflow generation tapi LLM untuk job reasoning?
  - Kenapa pakai shared state (97 field) dan bukan microservice terpisah?
- Ini menunjukkan penalaran ilmiah.

---

## Risiko #3 — Coverage Library dan Domain Library Tanpa Justifikasi

Sekarang `coverage_library.py` mendefinisikan 15 coverage dan `domain_detection_node.py` mendefinisikan 3 domain + library indicators. Tapi dari mana asalnya?

**Kenapa riskan:**
- Penguji akan tanya: "Kenapa 15 coverage? Kenapa bukan 10 atau 20? Dari mana daftar ini?"
- "Kenapa domain hanya e-commerce, blog, iot? Kenapa healthcare dan finance tidak?"
- "Siapa yang validasi library indicators (Stripe = e-commerce, MQTT = IoT)?"
- Tanpa justifikasi, ini terlihat seperti **arbitrary**.

**Cara perbaiki:**
- Jelaskan bahwa 15 coverage dirujuk dari **OWASP Top 10 (2021)** + **CWE Top 25** + **PCI-DSS** (untuk payment) sebagai landasan teori. Setiap coverage punya mapping ke standard yang jelas.
- Jelaskan bahwa 3 domain dipilih sebagai **variabel eksperimen** berdasarkan variasi attack surface yang signifikan (e-commerce = payment + user data, blog = content injection + XSS, iot = device auth + telemetry). Healthcare dan finance di luar scope karena batasan penelitian.
- Library indicators divalidasi melalui **analisis repositori open-source nyata** di masing-masing domain.
- Buat tabel mapping coverage → standard/OWASP di Bab II atau Bab III.

---

## Risiko #4 — Fallback Mechanism Tidak Dijustifikasi Secara Statistik

Di codebase, setiap LLM node punya fallback ke heuristic deterministic ketika LLM gagal. Tapi:

**Kenapa riskan:**
- Penguji bisa tanya: "Berapa persen kasus yang pakai fallback? Kalau 98% pakai fallback, berarti sistem Anda sebenarnya bukan AI tapi heuristic."
- "Threshold 0.50 dan 3.0 itu dari mana? Hasil eksperimen atau arbitrary?"
- Fallback yang tidak terukur membuat klaim "AI-powered" rentan.

**Cara perbaiki:**
- Jelaskan threshold sebagai **parameter eksperimen** yang divalidasi di Bab IV, bukan sebagai konstanta absolut.
- Di Bab III cukup sebutkan: "Threshold ditentukan melalui pilot test pada 2 repositori sampel. Hasil pilot test menunjukkan confidence LLM < 0.50 selalu salah klasifikasi, sehingga 0.50 dipilih sebagai batas minimum."
- Di Bab IV, laporkan persentase pemakaian fallback dari total 12 run sebagai metrik validasi tambahan.

---

## Risiko #5 — 18 Node, 97 State Fields = Kompleksitas Tanpa Justifikasi

**Kenapa riskan:**
- 18 node dengan 11 LLM calls adalah arsitektur yang kompleks. Penguji bisa tanya: "Kenapa tidak pakai 1 LLM call yang langsung generate YAML dari repo? Kenapa harus dipecah jadi 4 tahap 18 node?"
- 97 state fields terlihat seperti technical debt, bukan desain yang disengaja.

**Cara perbaiki:**
- Jelaskan alasan dekomposisi sebagai **chain-of-thought reasoning**: inference bertahap lebih akurat daripada single-pass generation. Riset LLM (Wei et al., 2022; Kojima et al., 2022) menunjukkan chain-of-thought meningkatkan akurasi reasoning.
- Jelaskan kenapa ada 4 tahap: setiap tahap adalah **abstraksi yang berbeda** (What repo? → What security? → What pipeline? → How good?).
- State field tidak perlu dijelaskan semua — cukup jelaskan **field kunci yang menjadi kontrak antar node**.

---

## Ranking Risiko

| # | Risiko | Severity | Kemungkinan Ditanyakan |
|---|--------|----------|------------------------|
| 1 | Prompt engineering bukan metode | **CRITICAL** | Hampir pasti |
| 2 | Tidak bisa bedakan metode vs implementasi | **CRITICAL** | Pasti (dosbing sudah warning) |
| 3 | Coverage/Domain library tanpa justifikasi | **HIGH** | Kalau penguji teliti |
| 4 | Fallback mechanism tanpa justifikasi statistik | **MEDIUM** | Kalau penguji paham ML |
| 5 | Kompleksitas node tanpa justifikasi dekomposisi | **MEDIUM** | Kalau penguji paham LLM/agent |

---

## Satu Kalimat Penyelamat

Kalau ada satu hal yang harus kamu fix sebelum sidang, itu adalah: **setiap kali kamu menulis sesuatu di Bab III, tanya dirimu: "Apakah ini menjelaskan KENAPA atau hanya menjelaskan APA?"** Kalau hanya menjelaskan APA — pindahkan ke Bab IV atau Lampiran.
