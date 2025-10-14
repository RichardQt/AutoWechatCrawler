/*
 Navicat Premium Data Transfer

 Source Server         : wsl_mysql_docker
 Source Server Type    : MySQL
 Source Server Version : 80043
 Source Host           : 172.24.25.220:3306
 Source Schema         : faxuan

 Target Server Type    : MySQL
 Target Server Version : 80043
 File Encoding         : 65001

 Date: 10/09/2025 10:26:16
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for fx_account_status
-- ----------------------------
DROP TABLE IF EXISTS `fx_account_status`;
CREATE TABLE `fx_account_status`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `account_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT '公众号标识',
  `account_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '公众号名称',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'PENDING' COMMENT '执行状态: PENDING/PROCESSING/COMPLETED/EXCEPTION/RETRYING',
  `last_update_time` datetime(0) NULL DEFAULT NULL COMMENT '最后更新时间',
  `retry_count` int(0) NOT NULL DEFAULT 0 COMMENT '重试次数',
  `last_exception_msg` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '最后异常信息',
  `next_retry_time` datetime(0) NULL DEFAULT NULL COMMENT '下次重试时间',
  `create_time` datetime(0) NULL DEFAULT NULL COMMENT '创建时间',
  `update_time` datetime(0) NULL DEFAULT NULL COMMENT '更新时间',
  `last_failed_date` date NULL DEFAULT NULL COMMENT '最后失败日期，用于补偿追踪',
  `compensation_priority` int(0) NULL DEFAULT 0 COMMENT '补偿优先级：0=正常，1=需要补偿，2=高优先级补偿',
  `failed_reason_backup` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '重置前的异常信息备份',
  `consecutive_failures` int(0) NULL DEFAULT 0 COMMENT '连续失败次数',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_account_id`(`account_id`) USING BTREE COMMENT '公众号标识唯一索引'
) ENGINE = InnoDB AUTO_INCREMENT = 259 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '公众号状态管理表' ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
