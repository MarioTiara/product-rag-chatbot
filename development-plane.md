Menurut saya, jangan langsung mengubah seluruh RAG kamu menjadi hybrid retrieval. Lebih baik dikembangkan secara bertahap dari arsitektur yang sudah ada: SQL-based product retrieval → keyword retrieval → vector retrieval → hybrid retrieval → reranking.

Dengan pendekatan ini, kamu bisa memahami fungsi setiap komponen, mengukur peningkatannya, dan menjadikan project `product-rag-chatbot` sebagai portofolio implementasi RAG yang lebih lengkap.

# Roadmap pengembangan Product RAG Chatbot

## Target arsitektur akhir

User Query

"Laptop untuk coding dan light gaming budget $700"

Agent / Query Understanding

Memahami kebutuhan, budget, dan kriteria

SQL Retrieval

Price, RAM, stock, brand

Hybrid Retrieval

BM25 + Vector Search

RRF Fusion + Reranker

Menggabungkan dan mengurutkan kandidat produk

SQL Product Detail + LLM Response

Mengambil data terbaru dan menghasilkan rekomendasi

Saya membagi pengerjaan menjadi 7 fase. Urutannya penting: setiap fase harus menghasilkan sesuatu yang bisa dites sebelum masuk ke fase berikutnya.

## Fase 0 — Persiapkan fondasi retrieval



Prioritas pertama

&#x20;Estimasi: 1–2 hari



Saat ini chatbot kamu sudah bisa menjawab:

- Harga laptop.
- Spesifikasi laptop.
- Ketersediaan dan stok.
- Pencarian produk berdasarkan atribut yang tersedia di SQL.

Jangan hilangkan kemampuan tersebut. SQL tetap menjadi sumber data utama untuk informasi faktual dan terstruktur.

Pekerjaan:

1. Audit kolom dataset produk yang tersedia.
2. Pastikan setiap konfigurasi produk memiliki identifier unik (`product_code`).
3. Pisahkan data produk asli dari dokumen untuk semantic retrieval.
4. Siapkan dataset evaluasi pertanyaan.

Contoh dataset evaluasi:

| Pertanyaan                                         | Jenis retrieval |
| -------------------------------------------------- | --------------- |
| Berapa harga Lenovo ThinkPad E14?                  | SQL             |
| Laptop RAM 16 GB di bawah $700                     | SQL             |
| Laptop untuk programming                           | Semantic        |
| Laptop untuk gaming ringan                         | Semantic        |
| Laptop untuk mahasiswa dan multitasking            | Semantic        |
| Laptop untuk coding dengan RAM 16 GB di bawah $700 | Hybrid          |

Output fase ini: Dataset produk yang siap digunakan dan kumpulan query untuk menguji kualitas retrieval.

## Fase 1 — Product Document Generation



Fondasi semantic search

&#x20;Estimasi: 2–3 hari



Di fase ini kamu akan membuat dokumen natural language dari data produk SQL.

Misalnya, data SQL:

```
{
  "product_code": "LEN-E14-001",
  "brand": "Lenovo",
  "model": "ThinkPad E14",
  "processor": "AMD Ryzen 7",
  "ram": "16 GB",
  "storage": "512 GB SSD"
}
```

Diubah menjadi:

```
{
  "product_code": "LEN-E14-001",
  "document": "Lenovo ThinkPad E14 is a business laptop powered by AMD Ryzen 7, with 16 GB RAM and 512 GB SSD storage. This configuration provides processing power and memory for software development, multitasking, and daily productivity."
}
```

Perlu dibedakan:

- Informasi spesifikasi berasal dari dataset.
- Use case seperti software development merupakan interpretasi berdasarkan spesifikasi, bukan klaim resmi produsen.

Pekerjaan:

1. Buat `ProductDocumentBuilder`.
2. Buat template deskripsi produk.
3. Tambahkan use case dan search keywords secara bertahap.
4. Simpan hasilnya ke `product_documents.json`.
5. Validasi agar tidak ada informasi spesifikasi yang dikarang.

Struktur modul:

```
app/
├── ingestion/
│   ├── product_document_builder.py
│   ├── product_enrichment_service.py
│   └── product_document_repository.py
```

Untuk tahap pertama, gunakan template Python biasa. Belum perlu menggunakan LLM untuk enrichment.

Output: Setiap produk mempunyai dokumen yang dapat digunakan untuk semantic retrieval.

## Fase 2 — Implementasi Keyword Retrieval (BM25)



Retrieval pertama

&#x20;Estimasi: 2–3 hari



Sebelum vector search, implementasikan BM25.

BM25 merupakan algoritma lexical retrieval yang mencari dokumen berdasarkan kecocokan kata dan relevansi term.

Contoh:

Query:

> Laptop Lenovo dengan Ryzen 7.

BM25 akan mencari dokumen yang memiliki kata-kata seperti:

- Lenovo
- Ryzen
- 7

Berbeda dengan SQL yang harus memahami struktur kolom tertentu, BM25 dapat mencari kecocokan kata di dalam keseluruhan dokumen produk.

Pekerjaan:

1. Pelajari cara kerja BM25.
2. Implementasikan menggunakan library `rank-bm25`.
3. Index seluruh `product_documents.json`.
4. Buat `BM25Retriever`.
5. Implementasikan fungsi `retrieve(query, top_k=10)`.
6. Uji dengan query yang memiliki variasi kata.

Struktur:

```
app/
└── retrieval/
    ├── base_retriever.py
    └── bm25_retriever.py
```

Contoh interface:

```
class BM25Retriever:    def retrieve(        self,        query: str,        top_k: int = 10    ) -> list[dict]:        ...
```

Output: Chatbot sudah mempunyai kemampuan mencari produk berdasarkan relevansi teks, bukan hanya filter SQL.

## Fase 3 — Implementasi Vector Retrieval dengan Qdrant



Semantic search

&#x20;Estimasi: 3–4 hari



Ini bagian penting untuk mencapai semantic retrieval.

Gunakan:

- Qdrant sebagai vector database.
- BGE-M3 sebagai embedding model.

Mengapa BGE-M3? Karena mendukung multilingual retrieval, termasuk bahasa Indonesia dan Inggris.

Pekerjaan:

1. Jalankan Qdrant menggunakan Docker.
2. Buat collection `products`.
3. Generate embedding dari setiap `document`.
4. Simpan embedding dan metadata ke Qdrant.
5. Implementasikan `VectorRetriever`.
6. Uji semantic search dengan berbagai query.

Contoh dokumen:

> Lenovo ThinkPad E14 is a business laptop suitable for software development and multitasking.

Query:

> I need a laptop for programming.

Meskipun kata `programming` tidak persis sama dengan `software development`, vector search diharapkan dapat menemukan hubungan semantik antara keduanya.

Contoh struktur payload Qdrant:

```
{
  "product_code": "LEN-E14-001",
  "document": "Lenovo ThinkPad E14 is...",
  "brand": "Lenovo",
  "model": "ThinkPad E14"
}
```

Harga dan stok tetap diambil dari SQL agar tidak menjadi data stale di vector database.

Struktur modul:

```
app/
├── embeddings/
│   └── embedding_service.py
└── retrieval/
    └── vector_retriever.py
```

Output: Chatbot sudah dapat menemukan produk berdasarkan makna query, bukan hanya kesamaan kata.

## Fase 4 — Implementasi Hybrid Retrieval



Target utama

&#x20;Estimasi: 3–4 hari



Sekarang kamu sudah punya dua retriever:

- BM25 untuk lexical retrieval.
- Vector search untuk semantic retrieval.

Gabungkan keduanya.

Contoh:

Query:

> Laptop untuk programming dengan Ryzen 7.

BM25 mungkin menemukan produk yang secara eksplisit menyebut Ryzen 7.

Vector search mungkin menemukan laptop yang deskripsinya menyebut software development atau coding.

Keduanya kemudian digabungkan.

Gunakan Reciprocal Rank Fusion (RRF).

RRF menggabungkan hasil berdasarkan ranking dari beberapa retriever.

Rumusnya:

\\[ RRF(d) = \sum\_{r \in R} \frac{1}{k + rank_r(d)} \\]

Keterangan:

- \\(d\\): dokumen produk.
- \\(R\\): kumpulan retriever.
- \\(rank_r(d)\\): posisi dokumen pada hasil retriever.
- \\(k\\): konstanta, umumnya 60.

Pekerjaan:

1. Buat `HybridRetriever`.
2. Jalankan BM25 dan Vector Retriever.
3. Gabungkan hasil dengan RRF.
4. Hilangkan duplikasi berdasarkan `product_code`.
5. Return top-K hasil gabungan.

Struktur:

```
app/
└── retrieval/
    ├── bm25_retriever.py
    ├── vector_retriever.py
    ├── hybrid_retriever.py
    └── fusion.py
```

Catatan: SQL filter seperti budget, RAM, dan stok tetap menjadi lapisan retrieval/filter terstruktur yang bekerja bersama hybrid retrieval. Secara definisi, hybrid retrieval yang kita implementasikan di sini adalah kombinasi lexical dan dense vector retrieval.

Output: Satu query dapat memanfaatkan pencarian berdasarkan kata dan makna sekaligus.

## Fase 5 — Implementasi Reranking



Peningkatan kualitas hasil

&#x20;Estimasi: 2–3 hari



Setelah RRF, kamu akan mempunyai kandidat produk. Namun, urutannya belum tentu paling relevan.

Di sinilah reranker digunakan.

Contohnya:

User:

> Laptop untuk coding, multitasking, dan light gaming.

Hybrid retrieval menghasilkan 10 produk.

Reranker akan menilai relevansi masing-masing produk terhadap query tersebut, lalu mengurutkannya kembali.

Kamu bisa mengeksplorasi:

- BGE Reranker.
- Cross-encoder reranker.

Pekerjaan:

1. Pelajari perbedaan bi-encoder dan cross-encoder.
2. Implementasikan `Reranker`.
3. Ambil top-10 dari Hybrid Retriever.
4. Rerank menjadi top-5.
5. Bandingkan hasil sebelum dan sesudah reranking.

Struktur:

```
app/
└── retrieval/
    └── reranker.py
```

Output: Produk yang paling relevan diharapkan berada di posisi teratas.

## Fase 6 — Integrasi ke AgentExecutor



Integrasi ke chatbot

&#x20;Estimasi: 2–3 hari



Setelah semua retriever bekerja secara independen, baru integrasikan dengan arsitektur agent kamu.

Saya menyarankan untuk tidak memasukkan seluruh logic retrieval ke dalam `AgentExecutor`.

Pertahankan tanggung jawabnya:

| Komponen             | Tanggung jawab                 |
| -------------------- | ------------------------------ |
| AgentExecutor        | Mengatur agent loop            |
| ToolCallHandler      | Mengeksekusi tool              |
| ProductSearchService | Mengatur pencarian produk      |
| HybridRetriever      | BM25 + Vector + RRF            |
| Reranker             | Mengurutkan kandidat           |
| ProductRepository    | Mengambil data produk dari SQL |

Buat tool baru misalnya:

```
recommend_products(    query: str,    max_price: float | None = None,    min_ram: int | None = None)
```

Alurnya:

1. User mengirim permintaan rekomendasi.
2. Agent memilih tool `recommend_products`.
3. ProductSearchService menjalankan hybrid retrieval.
4. SQL melakukan filter harga, RAM, dan stok.
5. Reranker mengurutkan hasil.
6. Detail produk terbaru diambil dari SQL.
7. Hasil diberikan kembali ke LLM.
8. LLM menyusun rekomendasi beserta alasan.

Dengan begitu, tool SQL yang sudah ada tetap bisa digunakan untuk pertanyaan harga dan spesifikasi biasa.

## Fase 7 — Evaluasi dan Observability



Penting untuk portofolio

&#x20;Estimasi: 2–3 hari



Jangan hanya mengukur apakah chatbot bisa menjawab. Kamu perlu membuktikan bahwa hybrid retrieval memang meningkatkan kualitas pencarian.

Bandingkan empat pendekatan:

1. SQL only.
2. BM25 only.
3. Vector only.
4. Hybrid (BM25 + Vector).
5. Hybrid + Reranker.

Metrik yang perlu dipelajari:

| Metrik       | Tujuan                                        |
| ------------ | --------------------------------------------- |
| Recall\@K    | Apakah produk relevan berhasil ditemukan?     |
| Precision\@K | Berapa banyak hasil yang relevan?             |
| MRR          | Seberapa tinggi posisi hasil relevan pertama? |
| NDCG\@K      | Seberapa baik urutan relevansi hasil?         |
| Latency      | Berapa lama retrieval berlangsung?            |

Kamu juga bisa memanfaatkan observability yang sudah kamu bangun untuk mencatat:

- Query user.
- Retrieval strategy.
- BM25 results.
- Vector results.
- RRF results.
- Reranker scores.
- Final products.
- Retrieval duration.

Ini akan membuat project kamu jauh lebih kuat karena bukan hanya mempunyai fitur RAG, tetapi juga bisa menunjukkan kualitas retrieval-nya.

## Estimasi pengerjaan

Jika dikerjakan sekitar 1 jam per hari:

| Fase                   | Estimasi   |
| ---------------------- | ---------- |
| 0. Persiapan data      | 1–2 hari   |
| 1. Document generation | 2–3 hari   |
| 2. BM25                | 2–3 hari   |
| 3. Vector retrieval    | 3–4 hari   |
| 4. Hybrid + RRF        | 3–4 hari   |
| 5. Reranking           | 2–3 hari   |
| 6. Agent integration   | 2–3 hari   |
| 7. Evaluation          | 2–3 hari   |
| Total                  | 17–25 hari |

Estimasi kasar, tidak termasuk waktu debugging dan eksplorasi model.

## Prioritas implementasi yang saya sarankan

Jangan kerjakan semuanya sekaligus. Berikut urutan milestone yang bisa kamu gunakan:

Project checklist

0/9 selesai

Audit dataset dan siapkan query evaluasi

Fase 0

Buat ProductDocumentBuilder dan JSON output

Fase 1

Implementasikan BM25Retriever

Fase 2

Setup Qdrant dan BGE-M3

Fase 3

Implementasikan VectorRetriever

Fase 3

Implementasikan HybridRetriever + RRF

Fase 4

Implementasikan Reranker

Fase 5

Integrasikan recommend_products ke AgentExecutor

Fase 6

Evaluasi dan bandingkan retrieval

Fase 7

Saran saya: mulai dari Fase 0 dan Fase 1. Jangan buru-buru install Qdrant atau BGE-M3 sebelum kamu mempunyai product documents yang berkualitas. Kualitas dokumen akan sangat memengaruhi hasil semantic retrieval.

Target akhirnya adalah chatbot yang tidak hanya menjawab "berapa harga laptop ini?", tetapi juga bisa memahami kebutuhan seperti "saya butuh laptop untuk backend development, Docker, dan sesekali bermain game dengan budget $700", menemukan produk yang relevan, lalu menjelaskan alasan rekomendasinya.