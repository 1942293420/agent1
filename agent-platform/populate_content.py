#!/usr/bin/env python3
"""填充 Skill.content - 匹配 ~/.hermes/skills/ 下的 SKILL.md"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agent_platform.settings')
django.setup()

from agents.models import Skill

# 建立 slug → SKILL.md 路径映射
# 文件结构: ~/.hermes/skills/{category}/{slug}/SKILL.md
slug_to_path = {}
for base in [
    os.path.expanduser('~/.hermes/skills'),
    os.path.expanduser('~/.hermes/profiles/feishu-bot2/skills'),
]:
    if not os.path.isdir(base):
        continue
    for root, dirs, files in os.walk(base):
        for f in files:
            if f == 'SKILL.md':
                # 目录名就是 slug
                parent_dir = os.path.basename(root)
                full_path = os.path.join(root, f)
                slug_to_path[parent_dir] = full_path
                # 也尝试用完整子路径名（有些 slug 包含连字符）
                rel = os.path.relpath(root, base)
                if '/' in rel:
                    alt_slug = rel.split('/')[-1]
                    slug_to_path[alt_slug] = full_path

print(f'找到 {len(slug_to_path)} 个 SKILL.md 文件')

filled = 0
skipped = 0

for skill in Skill.objects.all():
    if skill.content and len(skill.content) > 50:
        skipped += 1
        continue
    
    if skill.slug in slug_to_path:
        try:
            with open(slug_to_path[skill.slug], 'r', encoding='utf-8') as f:
                skill.content = f.read()
            skill.save(update_fields=['content'])
            filled += 1
        except Exception as e:
            print(f'  ✗ {skill.slug}: {e}')
            skipped += 1
    else:
        # 最后尝试：直接 glob 搜索
        import glob
        found = False
        for base in [
            os.path.expanduser('~/.hermes/skills'),
            os.path.expanduser('~/.hermes/profiles/feishu-bot2/skills'),
        ]:
            pattern = os.path.join(base, '**', skill.slug, 'SKILL.md')
            matches = glob.glob(pattern, recursive=True)
            if matches:
                try:
                    with open(matches[0], 'r', encoding='utf-8') as f:
                        skill.content = f.read()
                    skill.save(update_fields=['content'])
                    filled += 1
                    found = True
                except Exception as e:
                    pass
            if found:
                break
        
        if not found:
            skipped += 1

print(f'\n填充 {filled} 个，跳过 {skipped} 个')

# 最终统计
total = Skill.objects.count()
has = Skill.objects.exclude(content='').count()
print(f'总计: {total}, 有内容: {has}')
