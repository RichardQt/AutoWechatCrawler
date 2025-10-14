/*
 Navicat Premium Dump SQL

 Source Server         : faxuan
 Source Server Type    : MySQL
 Source Server Version : 80043 (8.0.43)
 Source Host           : localhost:3306
 Source Schema         : faxuan

 Target Server Type    : MySQL
 Target Server Version : 80043 (8.0.43)
 File Encoding         : 65001

 Date: 10/09/2025 15:32:46
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for fx_compensation_history
-- ----------------------------
DROP TABLE IF EXISTS `fx_compensation_history`;
CREATE TABLE `fx_compensation_history`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `account_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '公众号标识',
  `account_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '账户名称',
  `failed_date` date NOT NULL COMMENT '失败日期',
  `failure_reason` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '失败原因',
  `compensation_date` date NULL DEFAULT NULL COMMENT '补偿日期',
  `compensation_status` enum('PENDING','COMPLETED','FAILED') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT 'PENDING' COMMENT '补偿状态',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `unique_account_date`(`account_id` ASC, `failed_date` ASC) USING BTREE,
  INDEX `idx_compensation_status`(`compensation_status` ASC, `failed_date` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 77 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '补偿历史追踪表' ROW_FORMAT = DYNAMIC;

SET FOREIGN_KEY_CHECKS = 1;
