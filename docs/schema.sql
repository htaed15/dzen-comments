-- Схема БД проекта (MySQL-диалект) для импорта в MySQL Workbench:
-- File -> New Model -> File -> Import -> Reverse Engineer MySQL Create Script...
-- Затем File -> Save Model As... -> schema.mwb
-- (Фактически проект работает на PostgreSQL, структура таблиц та же.)

CREATE SCHEMA IF NOT EXISTS comments DEFAULT CHARACTER SET utf8mb4;
USE comments;

CREATE TABLE auth_user (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  username     VARCHAR(150) NOT NULL UNIQUE,
  email        VARCHAR(254) NOT NULL,
  password     VARCHAR(128) NOT NULL,
  date_joined  DATETIME NOT NULL
) ENGINE=InnoDB;

CREATE TABLE comments_author (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT NULL,
  user_name   VARCHAR(50)  NOT NULL,
  email       VARCHAR(254) NOT NULL,
  home_page   VARCHAR(200) NOT NULL DEFAULT '',
  ip_address  VARCHAR(45)  NOT NULL,
  user_agent  VARCHAR(300) NOT NULL DEFAULT '',
  created_at  DATETIME NOT NULL,
  INDEX idx_author_user_name (user_name),
  INDEX idx_author_email (email),
  CONSTRAINT fk_author_user FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE comments_comment (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  author_id   BIGINT NOT NULL,
  parent_id   BIGINT NULL,
  root_id     BIGINT NULL,
  text        TEXT NOT NULL,
  created_at  DATETIME NOT NULL,
  INDEX cmt_parent_created_idx (parent_id, created_at),
  INDEX cmt_root_created_idx (root_id, created_at),
  INDEX idx_comment_created (created_at),
  CONSTRAINT fk_comment_author FOREIGN KEY (author_id) REFERENCES comments_author (id) ON DELETE RESTRICT,
  CONSTRAINT fk_comment_parent FOREIGN KEY (parent_id) REFERENCES comments_comment (id) ON DELETE CASCADE,
  CONSTRAINT fk_comment_root   FOREIGN KEY (root_id)   REFERENCES comments_comment (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE comments_attachment (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  comment_id  BIGINT NOT NULL,
  file        VARCHAR(100) NOT NULL,
  kind        ENUM('image','text') NOT NULL,
  status      ENUM('processing','ready','failed') NOT NULL DEFAULT 'processing',
  INDEX idx_attachment_comment (comment_id),
  CONSTRAINT fk_attachment_comment FOREIGN KEY (comment_id) REFERENCES comments_comment (id) ON DELETE CASCADE
) ENGINE=InnoDB;
