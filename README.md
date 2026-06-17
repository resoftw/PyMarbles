# 2D Physics Marble Race Simulator & Editor 🌀✨

Sebuah simulator balapan kelereng (marble race) 2D interaktif berbasis fisika dengan gaya **Algodoo**, dikembangkan menggunakan **Pygame** untuk rendering grafis bertema *dark-neon* dan **Pymunk** sebagai engine simulasi fisika rigid-body yang presisi.

> [!NOTE]
> Proyek ini didevelop dan dipolish sepenuhnya melalui proses **Vibe Coding** menggunakan **Gemini 3.5 Flash** via **AGY (Antigravity-cli)**, asisten AI coding dari tim Google DeepMind.

---

## 🚀 Fitur Utama

### 🛠️ Map Editor Berkemampuan Penuh (Algodoo-Style)
*   **Dynamic Kinematic Escalator (Terbaru!)**: Anak tangga fisik sesungguhnya (tread horizontal & riser vertikal) yang berjalan mengangkut bola naik-turun menggunakan mekanika kinematic body dan wrapping posisi tanpa celah. Bola mendarat dan diam di atas anak tangga secara bebas mengikuti gravitasi nyata tanpa efek "lengket/lem".
*   **Obstacle & Komponen Ragam**:
    *   *Static Wall*: Dinding lintasan standar yang elastis dan bergesekan.
    *   *Polygonal Box*: Kotak rintangan statik atau dinamik (memiliki massa/berat).
    *   *Boost Pad / Accelerator*: Memberikan dorongan kecepatan instan pada kelereng.
    *   *Portal (Teleporter)*: Gerbang A-B yang memindahkan kelereng secara mulus dengan cooldown.
    *   *Elevator*: Lift bergerak naik-turun secara periodik dengan kecepatan dinamis.
    *   *Seesaw*: Papan jungkat-jungkit yang akan berputar balik arah jika tertabrak kelereng.
    *   *Spinner*: Kincir putar pasif atau aktif (bermotor) dengan jumlah baling-baling kustom.
    *   *Spawner*: Pemicu peluncuran kelereng periodik dengan warna acak/kustom.
    *   *Finish Line*: Garis sensor akhir untuk merekam urutan juara balapan.
*   **Figma-Like Transform Handles**: Memungkinkan rotasi, pergeseran posisi, pengubahan ukuran (scaling), serta snapping grid untuk kemudahan mendesain trek.
*   **Save/Load & Presets**: Simpan trek kustom Anda ke file JSON atau langsung coba peta preset bawaan (*Plinko*, *Loop-the-Loop*, *Portal Chaos*) serta fitur **Random Map Generator** untuk membuat trek acak instan yang mengalir sempurna.

### 🔊 Audio Spasial & Anti-Machinegun Effect
*   **Spatial Constant-Power Panning**: Suara benturan kelereng otomatis bergeser kiri-kanan sesuai posisi kamera secara halus.
*   **Doppler Pitch Shift**: Pitch suara disesuaikan secara real-time dengan kecepatan kelereng mendekat/menjauh dari viewport.
*   **Physics-Driven Volume & Pitch**: Volume suara disesuaikan dengan kekuatan impuls tabrakan (menggunakan kurva eksponensial $1.5$). Pitch suara divariasikan acak sebesar $\pm4\%$ di setiap benturan untuk menghilangkan efek machinegun (*machinegun effect*) yang monoton.
*   **Pre-cached Audio Resampling**: 7 variasi audio dimuat ke memori saat startup untuk performa gameplay 100% bebas lag.

### 📹 MP4 Video Exporter dengan Audio Sinkron
*   Perekaman real-time yang bersih: Menghilangkan semua panel editor, menu tombol, dan kisi-kisi grid, hanya mengekspor papan skor (leaderboard HUD) dan area balap kelereng.
*   Secara paralel merekam suara balapan dan menyatukannya ke dalam file `.mp4` menggunakan FFmpeg secara asynchronous di background setelah tombol rekam dimatikan.

---

## 🛠️ Instalasi & Persyaratan

Pastikan Anda telah menginstal **Python (versi 3.10 ke atas)** dan **FFmpeg** (untuk kebutuhan ekspor video).

1.  Clone atau salin repositori ini ke komputer Anda.
2.  Instal dependensi Python yang dibutuhkan:
    ```bash
    pip install pygame pymunk opencv-python numpy
    ```
3.  Pastikan `ffmpeg` tersedia di PATH sistem Anda (agar penyatuan audio-video otomatis berjalan lancar saat merekam).

---

## 🎮 Cara Menjalankan

Jalankan skrip utama dari direktori proyek menggunakan terminal atau PowerShell:

```bash
python main.py
```

---

## ⌨️ Kontrol Navigasi & Editor

*   **Edit / Race Mode**: Klik tombol **SIMULATE** di pojok kiri atas untuk memulai simulasi fisika, klik **EDIT** untuk kembali ke mode editor.
*   **Kamera (Panning & Zoom)**:
    *   Geser Viewport: Klik kanan atau klik tengah mouse lalu drag.
    *   Zoom: Scroll roda mouse ke atas/bawah.
    *   **CAM: FOLLOW / FREE**: Tombol di toolbar untuk mengaktifkan kamera mengikuti otomatis kelereng pemimpin balapan teratas secara halus.
*   **Transformasi Objek (Mode Edit)**:
    *   Gunakan alat **Select** (ikon panah atau tombol keyboard default) untuk memilih objek.
    *   Drag lingkaran cyan untuk memindahkan ujung segmen.
    *   Drag lingkaran magenta di atas kotak untuk memutar sudut objek.
    *   Drag kotak kuning di sudut untuk mengubah lebar/tinggi kotak rintangan.
    *   Klik **DELETE OBJECT** di panel inspektur kanan untuk menghapus objek yang sedang dipilih.

---

## 🧠 Vibe Coding Story
Aplikasi ini dirancang menggunakan konsep **Vibe Coding** yang difasilitasi oleh Gemini 3.5 Flash dan antarmuka CLI Antigravity (AGY). Seluruh perancangan matematis (seperti koordinat looping tangga eskalator, spatial panning audio, dan rendering terintegrasi) disempurnakan secara iteratif melalui arahan prompt natural bahasa Indonesia dan dieksekusi secara instan menjadi kode Python yang siap pakai.
