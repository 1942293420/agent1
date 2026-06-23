import os, re, hashlib, sys
sys.path.insert(0, '/home/jiangli/projects/agent-platform')
os.environ['DJANGO_SETTINGS_MODULE'] = 'agent_platform.settings'
import django
django.setup()
from agents.models import Skill

base_dirs = [
    '/home/jiangli/.hermes/profiles/feishu-bot2/skills',
    '/home/jiangli/.hermes/skills',
]

imported = 0
skipped = 0

for base in base_dirs:
    if not os.path.isdir(base):
        continue
    for root, dirs, files in os.walk(base):
        for f in files:
            if f != 'SKILL.md':
                continue
            filepath = os.path.join(root, f)
            # Derive slug from directory name
            dirname = os.path.basename(root)
            slug = dirname.lower().replace('_', '-').replace(' ', '-')[:128]

            # Derive category from path relative to base
            rel = os.path.relpath(root, base)
            parts = rel.split('/')
            category = parts[0] if len(parts) > 1 and parts[0] != '.' else ''

            # Read file content
            with open(filepath, 'r', encoding='utf-8') as fh:
                content = fh.read()

            # Extract name from frontmatter or first heading
            name = dirname.replace('-', ' ').replace('_', ' ').title()
            m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if m:
                name = m.group(1).strip()

            # Description: first paragraph after heading
            desc = ''
            lines = content.split('\n')
            in_content = False
            for line in lines:
                if line.startswith('# ') or line.startswith('## '):
                    in_content = True
                    continue
                if in_content and line.strip() and not line.startswith('```') and not line.startswith('---'):
                    desc = line.strip()[:200]
                    break

            # Hash
            file_hash = hashlib.sha256(content.encode()).hexdigest()

            # File size
            file_size = len(content.encode('utf-8'))

            try:
                skill, created = Skill.objects.update_or_create(
                    slug=slug,
                    defaults={
                        'name': name,
                        'description': desc[:500],
                        'category': category,
                        'source': 'local',
                        'status': 'active',
                        'version': '1.0.0',
                        'file_hash': file_hash,
                        'file_size': file_size,
                        'file_url': '',
                        'meyo_skill_id': None,
                    }
                )
                if created:
                    imported += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"Error on {slug}: {e}")

print(f"Imported: {imported}, Skipped (updated): {skipped}")
print(f"Total skills in DB: {Skill.objects.count()}")
