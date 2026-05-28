CREATE DATABASE IF NOT EXISTS tugas_akhir CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE tugas_akhir;

-- ##############################################################################
-- BAGIAN 1: ROLE PETUGAS MINIMARKET
-- ##############################################################################

-- 1. TABEL PETUGAS MINIMARKET
CREATE TABLE IF NOT EXISTS petugas_minimarket (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nama        VARCHAR(100)  NOT NULL,
    email       VARCHAR(100)  NOT NULL UNIQUE,
    kata_sandi  VARCHAR(255)  NOT NULL,
    nama_toko   VARCHAR(255)  DEFAULT 'Indomaret Pusat',
    telegram_id VARCHAR(50)   DEFAULT NULL,
    alamat      TEXT,
    lintang     VARCHAR(50)   DEFAULT NULL,
    bujur       VARCHAR(50)   DEFAULT NULL,
    dibuat_pada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. TABEL KAMERA
CREATE TABLE IF NOT EXISTS kamera (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    url_stream  VARCHAR(500),
    status      ENUM('online', 'offline') DEFAULT 'offline',
    dibuat_pada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 3. TABEL LAPORAN DETEKSI
CREATE TABLE IF NOT EXISTS deteksi (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    id_kamera     INT,
    jenis_benda   VARCHAR(100) NOT NULL,
    kepercayaan   FLOAT        NOT NULL DEFAULT 0.0,
    waktu         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    bukti         VARCHAR(500),
    id_petugas    INT DEFAULT 1,
    FOREIGN KEY (id_kamera) REFERENCES kamera(id) ON DELETE SET NULL,
    FOREIGN KEY (id_petugas) REFERENCES petugas_minimarket(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 4. TABEL NOTIFIKASI
CREATE TABLE IF NOT EXISTS notifikasi (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    id_deteksi    INT,
    jenis_benda   VARCHAR(100),
    kepercayaan   FLOAT,
    waktu         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bukti         VARCHAR(500),
    sudah_dibaca  TINYINT(1) DEFAULT 0,
    id_petugas    INT,
    FOREIGN KEY (id_deteksi) REFERENCES deteksi(id) ON DELETE SET NULL,
    FOREIGN KEY (id_petugas) REFERENCES petugas_minimarket(id) ON DELETE SET NULL
) ENGINE=InnoDB;


-- ##############################################################################
-- BAGIAN 2: ROLE PUSAT KEAMANAN (DATACENTER)
-- ##############################################################################

-- 1. TABEL PUSAT KEAMANAN
CREATE TABLE IF NOT EXISTS pusat_keamanan (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nama        VARCHAR(100)  NOT NULL,
    email       VARCHAR(100)  NOT NULL UNIQUE,
    kata_sandi  VARCHAR(255)  NOT NULL,
    dibuat_pada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. TABEL LAPORAN KEAMANAN (KHUSUS PUSAT KEAMANAN)
CREATE TABLE IF NOT EXISTS laporan_keamanan (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    id_deteksi    INT,
    id_kamera     INT,
    id_petugas    INT,
    nama_toko     VARCHAR(255),
    jenis_benda   VARCHAR(100) NOT NULL,
    kepercayaan   FLOAT        NOT NULL DEFAULT 0.0,
    waktu         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    bukti         VARCHAR(500),
    FOREIGN KEY (id_deteksi) REFERENCES deteksi(id) ON DELETE CASCADE,
    FOREIGN KEY (id_petugas) REFERENCES petugas_minimarket(id) ON DELETE SET NULL,
    FOREIGN KEY (id_kamera) REFERENCES kamera(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 3. TABEL NOTIFIKASI PUSAT KEAMANAN
CREATE TABLE IF NOT EXISTS notifikasi_pusat (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    id_laporan    INT,
    waktu         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bukti         VARCHAR(500),
    sudah_dibaca  TINYINT(1) DEFAULT 0,
    FOREIGN KEY (id_laporan) REFERENCES laporan_keamanan(id) ON DELETE CASCADE
) ENGINE=InnoDB;

DELIMITER $$
CREATE TRIGGER after_deteksi_insert
AFTER INSERT ON deteksi
FOR EACH ROW
BEGIN
    DECLARE v_nama_toko VARCHAR(255);
    DECLARE v_laporan_id INT;
    SELECT nama_toko INTO v_nama_toko FROM petugas_minimarket WHERE id = NEW.id_petugas;
    
    INSERT INTO laporan_keamanan (id_deteksi, id_kamera, id_petugas, nama_toko, jenis_benda, kepercayaan, waktu, bukti)
    VALUES (NEW.id, NEW.id_kamera, NEW.id_petugas, v_nama_toko, NEW.jenis_benda, NEW.kepercayaan, NEW.waktu, NEW.bukti);
    
    SET v_laporan_id = LAST_INSERT_ID();
    
    INSERT INTO notifikasi_pusat (id_laporan, sudah_dibaca)
    VALUES (v_laporan_id, 0);
END$$
DELIMITER ;

-- ==============================================================================
-- INSERT DATA AWAL (SEEDING)
-- ==============================================================================

-- DATA AWAL PETUGAS MINIMARKET
INSERT INTO petugas_minimarket (id, nama, email, kata_sandi, nama_toko, alamat, lintang, bujur) VALUES 
(1, 'Bowo', 'petugas@minimarket.com', 'scrypt:32768:8:1$uXYG1lUrVFtrrQet$bf052dc9365123971a16408ca7ed4a591b5067d1391b693fc0f564a8d1797ebf6ce1a4630244939bb85a233497a723ce044f3a8fc2b3bfad11a54affe51a45fd', 'Indomaret Pusat', 'Mliriprowo, Tarik, Sidoarjo, Java, 61352, Indonesia', '-7.443889', '112.470317'),
(2, 'prambaya', 'prambaya12@gmail.com', 'scrypt:32768:8:1$leHZAcMGaqfdE0HT$5717fd7620d98fe3e3fa63b7761c8787799af622cf54ec84deccc8cda53124b58adaf2fc531603f8df4efd16b49ce7d26ab1710993059280ef34f4ceaa347572', 'Sidoarjo', NULL, NULL, NULL);

-- DATA AWAL PUSAT KEAMANAN
INSERT INTO pusat_keamanan (id, nama, email, kata_sandi) VALUES 
(1, 'Admin Keamanan', 'PusatKeamanan12@gmail.com', 'scrypt:32768:8:1$LbNpv2g7cSudqbXm$fc741adae89bcecd13aed9d5daefb9d9c5bbb65fa30af7933295d42cec91475008a24e61a294f0cbc25617f8a280e2a6161768c55add5e7cf6ecc0f77edc1f26');

-- DATA AWAL KAMERA
INSERT INTO kamera (id, url_stream, status, dibuat_pada) VALUES 
(1, '', 'offline', '2026-04-07 00:40:35'),
(2, '', 'offline', '2026-04-07 00:40:35'),
(3, '', 'offline', '2026-04-07 00:40:35');

-- DATA AWAL LAPORAN DETEKSI
INSERT INTO deteksi (id, id_kamera, jenis_benda, kepercayaan, waktu, bukti, id_petugas) VALUES 
(106, NULL, 'Sabit', 0.694286, '2026-04-20 01:48:42', 'det_1776649722.jpg', 1),
(107, NULL, 'Sabit', 0.558473, '2026-04-23 05:21:46', 'det_1776921706.jpg', 1),
(108, NULL, 'Sabit', 0.694286, '2026-05-06 00:50:18', 'det_1778028618.jpg', 1);

-- DATA AWAL NOTIFIKASI
INSERT INTO notifikasi (id, id_deteksi, jenis_benda, kepercayaan, waktu, bukti, sudah_dibaca) VALUES 
(106, 106, 'Sabit', 0.694286, '2026-04-20 01:48:42', NULL, 1),
(107, 107, 'Sabit', 0.558473, '2026-04-23 05:21:46', NULL, 1),
(108, 108, 'Sabit', 0.694286, '2026-05-06 00:50:18', NULL, 1);

-- DATA AWAL NOTIFIKASI PUSAT KEAMANAN (Sinkronisasi status sudah_dibaca)
UPDATE notifikasi_pusat SET sudah_dibaca = 1 WHERE id_laporan IN (SELECT id FROM laporan_keamanan WHERE id_deteksi IN (106, 107, 108));
