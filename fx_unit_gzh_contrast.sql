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

 Date: 19/08/2025 00:49:02
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for fx_unit_gzh_contrast
-- ----------------------------
DROP TABLE IF EXISTS `fx_unit_gzh_contrast`;
CREATE TABLE `fx_unit_gzh_contrast`  (
  `unit_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `gzh_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of fx_unit_gzh_contrast
-- ----------------------------
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市纪委监委机关', '钟山清风');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市委组织部', '南京党建');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市委宣传部', '南京发布');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市委社会工作部', '南京社会工作');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市委网信办', '网信南京');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市委机要保密局', '南京市保密协会');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市法院', '南京市中级人民法院');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市检察院', '南京检察');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市发改委', '南京市发展和改革委员会');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市教育局', '南京教育发布');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市工信局', '南京市工信局');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市公安局', '南京警方');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市人社局', '南京人社');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市生态环境局', '南京生态环境');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市交通运输局', '南京交通');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市水务局', '南京水务');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市城管局', '南京市城管局');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市农业农村局', '南京美丽乡村');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市应急局', '南京应急管理');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市数据局', '南京市数据局');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市市场监管局', '南京市场监管');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市信访局', '南京市信访局');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市民宗局', '无');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市税务局', '南京税务');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市消防救援支队', '南京消防');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市总工会', '南京工会会员');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('团市委', '青春南京');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市妇联', '南京妇联');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市工商联', '新宁商');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('市残联', '南京市残疾人联合会');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('地铁集团', '南京地铁');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('南京市城市建设投资控股（集团）有限责任公司', '南京市城建控股公司');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('南京市交通建设投资控股（集团）有限责任公司', '南京市交通集团');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('南京市河西新城区国有资产经营控股(集团)有限责任公司', '河西集团');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('南京水务集团有限公司', '南京水务集团有限公司');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('南京大学', '南京大学');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('东南大学', '东南大学');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('南京工业大学', '南京工业大学');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('河海大学', '河海大学');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('南京师范大学', '南京师范大学');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('玄武区司法局', '法润玄武');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('秦淮区司法局', '秦淮司法行政');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('建邺区司法局', '南京建邺司法');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('鼓楼区司法局', '南京鼓楼政法');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('栖霞区司法局', '法润栖霞');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('雨花台区司法局', '雨花司法');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('江宁区司法局', '江宁司法');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('浦口区司法局', '浦口普法');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('六合区司法局', '六合智慧普法');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('溧水区司法局', '溧水普法');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('高淳区司法局', '高淳司法');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('江北新区综合治理局', '江北新区综合治理');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('中建安装集团有关公司', '中建安装南京公司');
INSERT INTO `fx_unit_gzh_contrast` VALUES ('南京扬子国资投资集团有限责任公司', '扬子国投');

SET FOREIGN_KEY_CHECKS = 1;
