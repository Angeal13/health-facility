-- ╔══════════════════════════════════════════════╗
-- ║  BIOKO HEALTH — Setup Base de Datos MySQL     ║
-- ║  Ejecutar como root de MySQL:                 ║
-- ║    mysql -u root -p < deploy/mysql_setup.sql  ║
-- ╚══════════════════════════════════════════════╝

-- Crear base de datos con UTF-8 completo (soporta caracteres especiales y emojis)
CREATE DATABASE IF NOT EXISTS bioko_health
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Usuario de aplicación (sin privilegios de sistema)
CREATE USER IF NOT EXISTS 'bioko_user'@'localhost'
    IDENTIFIED BY 'CAMBIAR_POR_PASSWORD_SEGURA';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP
    ON bioko_health.* TO 'bioko_user'@'localhost';

FLUSH PRIVILEGES;

-- Verificar
SELECT user, host FROM mysql.user WHERE user = 'bioko_user';
SHOW GRANTS FOR 'bioko_user'@'localhost';
