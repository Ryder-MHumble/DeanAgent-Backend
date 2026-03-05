#!/usr/bin/env python3
"""测试机构创建接口的三种场景."""
import json
import sys

import httpx

BASE_URL = "http://localhost:8001"


def test_scenario_1_create_university_only():
    """场景 1: 仅创建高校（不带院系）."""
    print("\n=== 场景 1: 仅创建高校 ===")

    payload = {
        "id": "test_univ_1",
        "name": "测试大学1",
        "type": "university",
        "category": "测试高校",
        "priority": "P3",
        "student_count_24": 10,
        "student_count_25": 15,
    }

    response = httpx.post(f"{BASE_URL}/api/v1/institutions/", json=payload, timeout=10)
    print(f"状态码: {response.status_code}")

    if response.status_code == 201:
        result = response.json()
        print(f"✅ 成功创建高校: {result['name']} (ID: {result['id']})")
        print(f"   院系数量: {len(result['departments'])}")
        return True
    else:
        print(f"❌ 失败: {response.text}")
        return False


def test_scenario_2_create_department_only():
    """场景 2: 仅创建院系（高校已存在）."""
    print("\n=== 场景 2: 仅创建院系（高校已存在）===")

    payload = {
        "id": "test_dept_1",
        "name": "测试学院1",
        "type": "department",
        "parent_id": "test_univ_1",  # 使用场景 1 创建的高校
    }

    response = httpx.post(f"{BASE_URL}/api/v1/institutions/", json=payload, timeout=10)
    print(f"状态码: {response.status_code}")

    if response.status_code == 201:
        result = response.json()
        print(f"✅ 成功创建院系: {result['name']} (ID: {result['id']})")
        print(f"   父高校: {result['parent_id']}")
        return True
    else:
        print(f"❌ 失败: {response.text}")
        return False


def test_scenario_3_create_university_with_departments():
    """场景 3: 创建高校 + 院系（一次性创建）."""
    print("\n=== 场景 3: 创建高校 + 院系（一次性）===")

    payload = {
        "id": "test_univ_2",
        "name": "测试大学2",
        "type": "university",
        "category": "测试高校",
        "priority": "P2",
        "departments": [
            {"id": "test_dept_2a", "name": "计算机学院"},
            {"id": "test_dept_2b", "name": "人工智能学院"},
            {"id": "test_dept_2c", "name": "软件学院"},
        ],
    }

    response = httpx.post(f"{BASE_URL}/api/v1/institutions/", json=payload, timeout=10)
    print(f"状态码: {response.status_code}")

    if response.status_code == 201:
        result = response.json()
        print(f"✅ 成功创建高校: {result['name']} (ID: {result['id']})")
        print(f"   院系数量: {len(result['departments'])}")
        for dept in result["departments"]:
            print(f"   - {dept['name']} (ID: {dept['id']})")
        return True
    else:
        print(f"❌ 失败: {response.text}")
        return False


def test_error_duplicate_university():
    """测试错误场景: 重复创建高校."""
    print("\n=== 错误场景: 重复创建高校 ===")

    payload = {
        "id": "test_univ_1",  # 已存在
        "name": "重复的测试大学",
        "type": "university",
    }

    response = httpx.post(f"{BASE_URL}/api/v1/institutions/", json=payload, timeout=10)
    print(f"状态码: {response.status_code}")

    if response.status_code == 409:
        print(f"✅ 正确返回 409 Conflict: {response.json()['detail']}")
        return True
    else:
        print(f"❌ 应该返回 409，实际返回: {response.status_code}")
        return False


def test_error_department_without_parent():
    """测试错误场景: 创建院系但不提供 parent_id."""
    print("\n=== 错误场景: 创建院系但不提供 parent_id ===")

    payload = {
        "id": "test_dept_orphan",
        "name": "孤儿院系",
        "type": "department",
        # 缺少 parent_id
    }

    response = httpx.post(f"{BASE_URL}/api/v1/institutions/", json=payload, timeout=10)
    print(f"状态码: {response.status_code}")

    if response.status_code == 400:
        print(f"✅ 正确返回 400 Bad Request: {response.json()['detail']}")
        return True
    else:
        print(f"❌ 应该返回 400，实际返回: {response.status_code}")
        return False


def test_error_department_parent_not_exist():
    """测试错误场景: 创建院系但父高校不存在."""
    print("\n=== 错误场景: 创建院系但父高校不存在 ===")

    payload = {
        "id": "test_dept_no_parent",
        "name": "无父院系",
        "type": "department",
        "parent_id": "nonexistent_university",
    }

    response = httpx.post(f"{BASE_URL}/api/v1/institutions/", json=payload, timeout=10)
    print(f"状态码: {response.status_code}")

    if response.status_code == 400:
        print(f"✅ 正确返回 400 Bad Request: {response.json()['detail']}")
        return True
    else:
        print(f"❌ 应该返回 400，实际返回: {response.status_code}")
        return False


def cleanup():
    """清理测试数据."""
    print("\n=== 清理测试数据 ===")

    test_ids = [
        "test_univ_1",
        "test_univ_2",
        "test_dept_1",
        "test_dept_2a",
        "test_dept_2b",
        "test_dept_2c",
    ]

    for inst_id in test_ids:
        response = httpx.delete(
            f"{BASE_URL}/api/v1/institutions/{inst_id}", timeout=10
        )
        if response.status_code == 204:
            print(f"✅ 删除成功: {inst_id}")
        elif response.status_code == 404:
            print(f"⚠️  不存在: {inst_id}")
        else:
            print(f"❌ 删除失败: {inst_id} (状态码: {response.status_code})")


def main():
    """运行所有测试."""
    print("=" * 60)
    print("机构创建接口测试 - 三种场景")
    print("=" * 60)

    results = []

    # 正常场景测试
    results.append(("场景1: 仅创建高校", test_scenario_1_create_university_only()))
    results.append(("场景2: 仅创建院系", test_scenario_2_create_department_only()))
    results.append(
        ("场景3: 创建高校+院系", test_scenario_3_create_university_with_departments())
    )

    # 错误场景测试
    results.append(("错误: 重复创建高校", test_error_duplicate_university()))
    results.append(("错误: 院系缺少parent_id", test_error_department_without_parent()))
    results.append(("错误: 父高校不存在", test_error_department_parent_not_exist()))

    # 清理
    cleanup()

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print("\n❌ 无法连接到服务器，请确保后端服务正在运行:")
        print("   uvicorn app.main:app --reload")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
