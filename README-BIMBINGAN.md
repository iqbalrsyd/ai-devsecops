# Ringkasan Bimbingan & Tindak Lanjut Naskah

**Tanggal:** 1 Juli 2026
**Pembimbing:** Ridi Ferdiana
**Durasi:** 18m 10s

---

## A. Ringkasan Poin Bimbingan

### 1. Perubahan Fokus Utama: Arsitektur → Domain
- Dulu fokus pada perbandingan **arsitektur (monolith vs microservices)**
- Sekarang fokus pada **DOMAIN** sebagai variabel eksperimen
- Arsitektur tetap dideteksi tetapi bukan variabel pembeda
- Cari sampel microservices di salah satu domain untuk keberagaman

### 2. Desain Pengujian Baru
| Aspek | Spesifikasi |
|-------|-------------|
| Jumlah pengujian | **3 kali** dengan kategori teknologi berbeda |
| Jumlah domain | **4 domain** |
| Domain | Internet System (e-commerce), Business System, Information System, General |
| Sampling | Random sampling — bahasa pemrograman **tidak disamakan** |
| Jumlah repo | **1 per domain** (total 4 repositori) |
| Kriteria repo | **Well-known system** yang banyak digunakan |
| Contoh | E-commerce → Shopify; Business → source code model; Information System → Wordpress; General → aplikasi sendiri |

### 3. Ground Truth untuk Validasi
- Gunakan **versi LAMA** source code (yang belum di-patch)
- Evaluasi apakah sistem bisa **membangkitkan otomatis** ukuran security
- Lihat **kelengkapan** dan **konsistensi**: ada yang miss?
- Bandingkan hasil antar model pengukuran kode — apa perbedaannya?
- Evaluasi fungsional: sistem jalan atau tidak
- Evaluasi non-fungsional: **code coverage**, rekomendasi **benar atau tidak**

### 4. Struktur Bab
- ~~Bab 5 implementasi~~ → **Dipindah ke akhir Bab 4**
- Bab 4 akhir: arsitektur sistem, diagram arsitektur, database, proses deployment, framework
- Bab 5 → **Kesimpulan**
- Naskah perlu dirapikan total ("tulisan belum jadi")

### 5. Arahan Makalah
| Komponen | Deskripsi |
|----------|-----------|
| **Masalah** | Kenapa masalah penting bagi developer? |
| **Existing solutions** | Solusi yang sudah ada seperti apa? |
| **Your solution** | Solusi kamu seperti apa, bedanya di mana? |
| **Metode** | Metode untuk mengembangkan solusi |
| **Hasil & Manfaat** | Hasilnya apa, manfaatnya untuk apa |

### 6. Deadline
- Naskah revisi hari ini (1 Juli)
- Review besok (2 Juli)
- Approve sebelum **jam 12:00** untuk maju (sidang)

---

## B. Kesenjangan dengan Naskah Saat Ini (Bab 1, 2, 3, 5)

### Bab 1: Pendahuluan
| Poin Bimbingan | Kondisi Naskah Saat Ini | Tindakan |
|----------------|------------------------|----------|
| Fokus pada **domain**, bukan arsitektur | Masih menekankan perbandingan monolith vs microservices sebagai kontribusi utama | Ubah rumusan masalah, tujuan, dan kontribusi ke arah **domain-aware security coverage pipeline** |
| 4 domain sebagai variabel eksperimen | Belum ada deskripsi domain sampling | Tambahkan domain classification framework |
| Pengujian 3 kali dengan teknologi berbeda | Masih merujuk 40 repositori (20 monolith + 20 microservices) | Ubah desain eksperimen: **4 repositori × 3 pengujian = 12 run** |
| "Sistem yang well-known" | Tidak disebut | Tambah kriteria pemilihan repositori |

### Bab 2: Tinjauan Pustaka
| Poin Bimbingan | Kondisi Naskah Saat Ini | Tindakan |
|----------------|------------------------|----------|
| Perbandingan antar model pengukuran kode | Mungkin sudah ada landasan teori SAST/DAST/SCA | Perkuat tinjauan tentang **security coverage models** dan **domain-specific security** |
| Validitas: bagaimana menentukan rekomendasi benar/salah | Kurang pembahasan ground truth | Tambah metodologi **ground truth** menggunakan versi lama source code |
| | Belum ada referensi sistem well-known | Tambah studi tentang Shopify, Wordpress dll sebagai reference systems |

### Bab 3: Metode Penelitian
| Poin Bimbingan | Kondisi Naskah Saat Ini | Tindakan |
|----------------|------------------------|----------|
| **PERUBAHAN BESAR**: 4 domain × 1 repo | Masih pakai desain 40 repositori (20+20) | **Ubah total desain eksperimen** |
| Random sampling — bahasa tidak disamakan | Mungkin masih pakai JS/TS homogen | Hapus homogenitas bahasa — random sampling |
| Ground truth: versi lama yang belum di-patch | Tidak dibahas | Tambah prosedur **version rollback** untuk validasi |
| Evaluasi: coverage, konsistensi, rekomendasi benar | Mungkin hanya bahas akurasi deteksi | Tambah **3 dimensi evaluasi**: coverage, consistency, recommendation correctness |
| Arsitektur bukan variabel — tapi tetap dideteksi | Arsitektur sebagai variabel utama | Ubah: arsitektur sebagai **konteks**, domain sebagai **variabel** |
| | | Tambah **3 kali pengujian** dengan teknologi SAST/SCA/secret-scan berbeda |

### Bab 5: Kesimpulan
| Poin Bimbingan | Kondisi Naskah Saat Ini | Tindakan |
|----------------|------------------------|----------|
| ~~Bab 5~~ → **pindah ke akhir Bab 4** | Bab 5 berisi implementasi sistem | Pindahkan konten implementasi ke Bab 4; Bab 5 jadi **kesimpulan** |
| Belum ada konten untuk Bab 5 yang baru | — | Tulis kesimpulan berdasarkan hasil pengujian 4 domain |

---

## C. Keterkaitan dengan Rencana Pembuatan

### Bab 4: Hasil dan Implementasi
- **Bagian akhir Bab 4**: Implementasi sistem secara lengkap
  - Arsitektur sistem
  - Diagram arsitektur
  - Database schema
  - Proses deployment
  - Framework yang digunakan
- **Hasil pengujian 4 domain** dengan 3 kategori teknologi
  - Analisis per-domain: coverage, konsistensi, perbedaan hasil
  - Perbandingan hasil antar teknologi pengujian
  - Analisis rekomendasi: benar/salah berdasarkan ground truth versi lama

### Bab 6: Penutup (dulu Bab 5)
- **Kesimpulan** berdasarkan hasil pengujian
  - Apakah sistem bisa membangkitkan ukuran security secara otomatis?
  - Coverage dan konsistensi antar domain
  - Perbedaan hasil antar model pengukuran
- **Saran** untuk pengembangan selanjutnya

### Makalah
**Struktur makalah sesuai arahan Pak Ridi:**

| Section | Konten |
|---------|--------|
| **1. Pendahuluan** | Kenapa masalah security coverage penting bagi developer? |
| **2. Existing Solutions** | Solusi yang sudah ada: Semgrep, GitHub CodeQL, Snyk, dll — bagaimana mereka menentukan coverage? |
| **3. Proposed Solution** | Domain-aware security coverage pipeline — bedanya: otomatis, konteks-aware, 15 security coverages |
| **4. Metode** | 4 domain × 3 teknologi pengujian, ground truth versi lama, evaluasi coverage + konsistensi |
| **5. Hasil** | Temuan dari 4 domain — coverage, konsistensi, kualitas rekomendasi |
| **6. Manfaat** | Untuk developer: pipeline security yang adaptif dan konteks-aware |

---

## D. Action Items Prioritas

| # | Item | Urgensi | Terkait |
|---|------|---------|---------|
| 1 | Ubah desain eksperimen: 4 domain × 1 repo × 3 pengujian | 🔴 KRITIS | Bab 1, 3 |
| 2 | Pindahkan implementasi dari Bab 5 ke akhir Bab 4 | 🔴 KRITIS | Bab 4, 5 |
| 3 | Tulis ulang Bab 5 jadi kesimpulan | 🔴 KRITIS | Bab 5 (baru) |
| 4 | Cari 4 repositori well-known + versi lama untuk ground truth | 🟡 HIGH | Bab 3, 4 |
| 5 | Perbaiki narasi dari "arsitektur" ke "domain" | 🟡 HIGH | Bab 1, 2, 3 |
| 6 | Siapkan draft makalah sesuai struktur | 🟡 HIGH | Makalah |
| 7 | Tambah 3 dimensi evaluasi (coverage, consistency, correctness) | 🟡 MEDIUM | Bab 3, 4 |
| 8 | Rapikan tulisan secara keseluruhan | 🟡 MEDIUM | Semua bab |
| 9 | Kirim naskah lengkap ke Pak Ridi untuk review | 🔴 KRITIS | Deadline |
