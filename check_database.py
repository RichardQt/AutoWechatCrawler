#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库表结构和最近的数据
"""

from src.database.database_manager import DatabaseManager

def check_database():
    db = DatabaseManager(host='127.0.0.1', port=3306, user='root', password='123456', database='faxuan')
    cursor = db.connection.cursor()
    
    # 检查表结构
    print("=== 数据库表 fx_article_records 的字段 ===")
    cursor.execute('DESCRIBE fx_article_records')
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col['Field']} - {col['Type']} - {'NULL' if col['Null'] == 'YES' else 'NOT NULL'}")
    
    # 检查最近的数据
    print("\n=== 最近5条记录的单位名称 ===")
    cursor.execute('SELECT unit_name, article_title, create_time FROM fx_article_records ORDER BY create_time DESC LIMIT 5')
    recent = cursor.fetchall()
    for row in recent:
        print(f"单位: {row.get('unit_name', 'NULL')} | 时间: {row['create_time']} | 标题: {row['article_title'][:50]}...")
    
    db.disconnect()

if __name__ == "__main__":
    check_database()