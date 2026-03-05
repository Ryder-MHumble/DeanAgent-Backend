"""AMiner API 使用示例

本模块提供 AMiner 学者和机构信息查询功能。
数据存储在 data/aminer_organizations.json，使用统一的结构。
"""
import asyncio

from app.services.aminer_service import get_aminer_service


async def example_list_organizations():
    """示例 1: 列出所有支持的机构"""
    service = get_aminer_service()
    orgs = service.list_all_orgs()

    print(f"共支持 {len(orgs)} 所机构")
    for org in orgs[:5]:
        print(f"  - {org['name_zh']} ({org['name_en']})")
        if org.get('org_id'):
            print(f"    org_id: {org['org_id']}")


async def example_get_organization():
    """示例 2: 查询指定机构信息（从本地 JSON）"""
    service = get_aminer_service()
    org_info = service.get_org_from_cache("清华大学")

    if org_info:
        print(f"机构: {org_info['name_zh']}")
        print(f"英文名: {org_info['name_en']}")
        print(f"org_id: {org_info['org_id']}")
        print(f"org_name: {org_info['org_name']}")
    else:
        print("机构未找到，请先添加")


async def example_add_organization():
    """示例 3: 添加新机构（调用 AMiner API）"""
    service = get_aminer_service()

    # 添加新机构（如果已存在则返回现有数据）
    org_info = await service.add_organization(
        org_name_zh="麻省理工学院",
        org_name_en="Massachusetts Institute of Technology"
    )

    if org_info:
        print(f"✓ 机构已添加: {org_info['name_zh']}")
        print(f"  org_id: {org_info['org_id']}")
    else:
        print("✗ 添加失败")


async def example_query_scholar():
    """示例 4: 查询学者完整信息"""
    service = get_aminer_service()

    # 查询学者
    scholar = await service.get_scholar_full_info(
        scholar_name="姚期智",
        org_name_zh="清华大学"
    )

    if scholar:
        print(f"学者: {scholar['name_zh']} ({scholar['name']})")
        print(f"机构: {scholar['org_zh']}")
        print(f"person_id: {scholar['person_id']}")
        print(f"引用数: {scholar['n_citation']}")
        print(f"研究兴趣: {', '.join(scholar['interests'][:3])}")

        if scholar.get('bio_zh'):
            print(f"简介: {scholar['bio_zh'][:100]}...")
    else:
        print("✗ 学者未找到")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("示例 1: 列出所有机构")
    print("=" * 60)
    await example_list_organizations()

    print("\n" + "=" * 60)
    print("示例 2: 查询指定机构")
    print("=" * 60)
    await example_get_organization()

    print("\n" + "=" * 60)
    print("示例 3: 添加新机构")
    print("=" * 60)
    await example_add_organization()

    print("\n" + "=" * 60)
    print("示例 4: 查询学者信息")
    print("=" * 60)
    await example_query_scholar()


if __name__ == "__main__":
    asyncio.run(main())
