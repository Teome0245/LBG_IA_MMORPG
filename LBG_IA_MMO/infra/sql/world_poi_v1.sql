-- World POI v1 — éditeur monde Prime (ADR 0008)
-- Appliquer sur MariaDB Prime avant Phase 0 du world editor.
-- Doc : docs/world_editor_plan.md

CREATE TABLE IF NOT EXISTS world_poi (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  poi_id          VARCHAR(64) NOT NULL UNIQUE COMMENT 'ex. poi:mos_eisley_training_center',
  zone            VARCHAR(32) NOT NULL DEFAULT 'tatooine',
  label           VARCHAR(128) NOT NULL,
  structure_template VARCHAR(255) NOT NULL COMMENT 'chemin template IFF Core3',
  object_id       BIGINT UNSIGNED NULL COMMENT 'OID structure apres spawn',
  world_x         FLOAT NOT NULL,
  world_y         FLOAT NOT NULL,
  world_z         FLOAT NOT NULL,
  heading         FLOAT NOT NULL DEFAULT 0,
  root_cell_id    BIGINT UNSIGNED NULL,
  status          ENUM('draft','active','removed') NOT NULL DEFAULT 'draft',
  roster_links    JSON NULL,
  meta_json       JSON NULL,
  created_by      VARCHAR(64) NULL,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_zone_status (zone, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS world_poi_npc_slot (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  poi_id          VARCHAR(64) NOT NULL,
  slot_key        VARCHAR(64) NOT NULL,
  pilot_id        VARCHAR(64) NULL,
  roster_id       VARCHAR(64) NULL,
  mobile_template VARCHAR(64) NOT NULL,
  cell_id         BIGINT UNSIGNED NOT NULL DEFAULT 0,
  x               FLOAT NOT NULL,
  y               FLOAT NOT NULL,
  z               FLOAT NOT NULL,
  heading         FLOAT NOT NULL DEFAULT 0,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_poi_slot (poi_id, slot_key),
  CONSTRAINT fk_world_poi_npc_slot_poi
    FOREIGN KEY (poi_id) REFERENCES world_poi(poi_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
