"""
Django management command: sync meyo skills

用法:
  python manage.py sync_meyo_skills [--dry-run] [--tag backend]

逻辑:
  1. 从 Meyo 社区拉取技能列表
  2. 与本地 skill_registry 比对
  3. 新增/更新技能元数据
  4. 输出同步报告
"""
import json, sys, time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from django.core.management.base import BaseCommand
from django.utils import timezone

from agents.models import Skill


MEYO_API_BASE = 'https://www.meyo123.com/api/v1'
MEYO_SKILL_VERSION = '1.0.0'
REQUEST_DELAY = 1.0  # seconds between requests (avoid 429)


class Command(BaseCommand):
    help = '从 Meyo 社区同步技能到本地 skill_registry'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='仅展示变更，不写入数据库')
        parser.add_argument('--tag', type=str, default='',
                            help='按标签筛选（如 backend, django, developer）')
        parser.add_argument('--keyword', type=str, default='backend',
                            help='搜索关键词')
        parser.add_argument('--api-key', type=str, default='',
                            help='Meyo API Key（默认从凭证文件读取）')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tag = options['tag']
        keyword = options['keyword']
        api_key = self._get_api_key(options['api_key'])

        if not api_key:
            self.stderr.write(self.style.ERROR(
                '未找到 Meyo API Key。请确保 ~/.hermes/meyo/credentials.json 存在且包含 api_key'
            ))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS(f'\U0001f50d 正在同步 Meyo 技能... (tag={tag or "all"}, keyword={keyword})'))

        # Step 1: 拉取技能列表
        try:
            skills = self._fetch_skills(api_key, tag, keyword)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'拉取技能列表失败: {e}'))
            sys.exit(1)

        self.stdout.write(f'   从 Meyo 获取到 {len(skills)} 个技能')

        # Step 2: 比对 & 同步
        created, updated, skipped = 0, 0, 0
        for skill_data in skills:
            result = self._sync_skill(skill_data, dry_run)
            if result == 'created':
                created += 1
            elif result == 'updated':
                updated += 1
            else:
                skipped += 1

        # Step 3: 输出报告
        self.stdout.write(self.style.SUCCESS(
            f'\u2705 同步完成: 新增 {created} | 更新 {updated} | 跳过 {skipped}'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('   (dry-run 模式，未实际写入)'))

    def _get_api_key(self, cli_key: str) -> str:
        if cli_key:
            return cli_key
        # 从凭证文件读取
        import os
        cred_path = os.path.expanduser('~/.hermes/meyo/credentials.json')
        try:
            with open(cred_path) as f:
                return json.load(f).get('api_key', '')
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return ''

    def _fetch_skills(self, api_key: str, tag: str, keyword: str) -> list:
        """拉取 Meyo 技能列表"""
        all_skills = []
        page = 1

        while True:
            if tag:
                url = f'{MEYO_API_BASE}/skills?sort=downloadCount&tag={tag}&page={page}'
            else:
                url = f'{MEYO_API_BASE}/skills/search?keyword={keyword}&page={page}'

            req = Request(url)
            req.add_header('Authorization', f'Bearer {api_key}')
            req.add_header('X-Skill-Version', MEYO_SKILL_VERSION)
            req.add_header('X-Trigger-Source', 'self-explore')
            req.add_header('X-Trigger-Reason', 'Daily scheduled skill registry sync')

            try:
                with urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())

                # API returns {code, message, data: {total, page, pageSize, list: [...]}}
                # data may be null on out-of-range pages
                data_obj = data.get('data')
                if not data_obj:
                    break
                items = data_obj.get('list', [])
                if not items:
                    break

                all_skills.extend(items)
                page += 1
                time.sleep(REQUEST_DELAY)

            except HTTPError as e:
                if e.code == 429:
                    retry = int(e.headers.get('Retry-After', '30'))
                    self.stdout.write(self.style.WARNING(f'   限流，等待 {retry}s...'))
                    time.sleep(retry)
                    continue
                elif e.code == 404:
                    break  # 最后一页
                else:
                    raise
            except URLError as e:
                self.stderr.write(f'   网络错误: {e}')
                break

        return all_skills

    def _sync_skill(self, skill_data: dict, dry_run: bool) -> str:
        """同步单个技能"""
        name = skill_data.get('name', '')
        slug = skill_data.get('slug', name.lower().replace(' ', '-'))
        # API returns int id, model expects char
        meyo_id = str(skill_data.get('id', ''))

        if not name:
            return 'skipped'

        # Look up existing skill: first by meyo_skill_id, then by slug
        try:
            local = Skill.objects.get(meyo_skill_id=meyo_id)
        except Skill.DoesNotExist:
            try:
                local = Skill.objects.get(slug=slug)
            except Skill.DoesNotExist:
                local = None

        # Derive category from first tag if not explicit
        tags = skill_data.get('tags', [])
        category = skill_data.get('category', '')
        if not category and tags:
            category = tags[0]

        defaults = {
            'name': name,
            'slug': slug,
            'description': skill_data.get('description', ''),
            'version': str(skill_data.get('latestVersion', '1.0.0')),
            'category': category,
            'source': Skill.Source.MEYO,
            'status': Skill.Status.ACTIVE,
            'meyo_skill_id': meyo_id,
            'last_synced_at': timezone.now(),
            'tags': tags,
            'file_url': skill_data.get('sourceUrl', skill_data.get('download_url', '')),
            'file_hash': skill_data.get('file_hash', skill_data.get('checksum', '')),
            'file_size': skill_data.get('file_size', 0),
        }

        if local is None:
            # 全新技能
            if not dry_run:
                Skill.objects.create(**defaults)
            self.stdout.write(f'   \u2795 {name} (new skill)')
            return 'created'
        else:
            # 检查是否需要更新
            current_ver = local.version
            new_ver = defaults['version']
            if current_ver != new_ver:
                if not dry_run:
                    for key, value in defaults.items():
                        setattr(local, key, value)
                    local.save()
                self.stdout.write(f'   \U0001f504 {name} v{current_ver} \u2192 v{new_ver}')
                return 'updated'
            else:
                # 更新时间戳
                if not dry_run:
                    local.last_synced_at = timezone.now()
                    local.save(update_fields=['last_synced_at'])
                return 'skipped'
