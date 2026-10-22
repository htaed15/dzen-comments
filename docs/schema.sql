-- Схема БД проекта (MySQL-диалект) для импорта в MySQL Workbench:
-- File -> New Model -> File -> Import -> Reverse Engineer MySQL Create Script...
-- Затем File -> Save Model As... -> schema.mwb
-- (Фактически проект работает на PostgreSQL, структура таблиц та же.)
--
-- Уникальность имени и e-mail без учёта регистра в приложении обеспечивается
-- уникальными индексами по LOWER(...); в MySQL при регистронезависимой
-- сортировке (utf8mb4_0900_ai_ci) это даёт обычный UNIQUE.

CREATE SCHEMA IF NOT EXISTS comments DEFAULT CHARACTER SET utf8mb4;
USE comments;

CREATE TABLE auth_user (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  username     VARCHAR(150) NOT NULL UNIQUE,
  email        VARCHAR(254) NOT NULL,
  password     VARCHAR(128) NOT NULL,          -- хеш пароля, не сам пароль
  date_joined  DATETIME NOT NULL
) ENGINE=InnoDB;

-- Профиль: создаётся при регистрации или первом сообщении под новым именем.
-- user_id пустой у гостей (без регистрации).
CREATE TABLE comments_profile (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT NULL UNIQUE,
  username    VARCHAR(50)  NOT NULL UNIQUE,    -- уникальное имя
  email       VARCHAR(254) NOT NULL UNIQUE,    -- один e-mail = одно имя
  home_page   VARCHAR(200) NOT NULL DEFAULT '',
  created_at  DATETIME NOT NULL,
  CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES auth_user (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE comments_comment (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  profile_id    BIGINT NOT NULL,
  parent_id     BIGINT NULL,                   -- кому ответили
  root_id       BIGINT NULL,                   -- корень ветки
  text          TEXT NOT NULL,
  is_anonymous  TINYINT(1) NOT NULL DEFAULT 0, -- автор известен системе, но скрыт публично
  ip_address    VARCHAR(45)  NOT NULL,         -- данные для идентификации клиента
  user_agent    VARCHAR(300) NOT NULL DEFAULT '',
  created_at    DATETIME NOT NULL,
  INDEX cmt_parent_created_idx (parent_id, created_at),
  INDEX cmt_root_created_idx (root_id, created_at),
  INDEX cmt_profile_created_idx (profile_id, created_at),
  INDEX idx_comment_created (created_at),
  CONSTRAINT fk_comment_profile FOREIGN KEY (profile_id) REFERENCES comments_profile (id) ON DELETE RESTRICT,
  CONSTRAINT fk_comment_parent  FOREIGN KEY (parent_id)  REFERENCES comments_comment (id) ON DELETE CASCADE,
  CONSTRAINT fk_comment_root    FOREIGN KEY (root_id)    REFERENCES comments_comment (id) ON DELETE CASCADE
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
