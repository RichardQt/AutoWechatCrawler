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

 Date: 10/09/2025 18:06:29
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for fx_crawl_exception
-- ----------------------------
DROP TABLE IF EXISTS `fx_crawl_exception`;
CREATE TABLE `fx_crawl_exception`  (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `finished_date` datetime NULL DEFAULT NULL COMMENT '批处理完成日期',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '状态: unfinished/finished',
  `create_time` datetime NULL DEFAULT NULL COMMENT '创建时间',
  `update_time` datetime NULL DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `ix_fx_crawl_exception_exception_date`(`finished_date` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 9 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Records of fx_crawl_exception
-- ----------------------------
INSERT INTO `fx_crawl_exception` VALUES (1, '2025-08-21 11:42:55', 'finished', '2025-08-21 11:43:12', '2025-08-21 11:43:14');

SET FOREIGN_KEY_CHECKS = 1;
