# restapi/management/commands/test_linkedin_api.py

import requests
import urllib.parse
from django.core.management.base import BaseCommand
from restapi.models import SocialAccount, Clinic
from datetime import datetime, timedelta

LI_VERSION = '202509'

ANALYTICS_FIELDS = (
    'impressions,clicks,landingPageClicks,costInLocalCurrency,'
    'externalWebsiteConversions,likes,shares,comments,'
    'videoViews,follows,opens,'
    'dateRange,pivotValues'
)


# ---------------- HELPERS ---------------- #

def encode_urn(urn: str) -> str:
    return urn.replace(':', '%3A')


def build_analytics_url(params: dict) -> str:
    parts = []
    for key, value in params.items():
        value_str = str(value)

        if key in ('campaigns', 'accounts', 'creatives'):
            inner = value_str[len('List('):-1]
            urns = inner.split(',')
            encoded_urns = ','.join(encode_urn(u.strip()) for u in urns)
            encoded_value = f'List({encoded_urns})'
        elif key in ('dateRange', 'fields'):
            encoded_value = value_str
        else:
            encoded_value = urllib.parse.quote(value_str, safe='')

        parts.append(f'{key}={encoded_value}')

    return f'https://api.linkedin.com/rest/adAnalytics?{"&".join(parts)}'


def get_currency_symbol(currency):
    return {'USD': '$', 'INR': '₹'}.get(currency, currency + ' ')


# ---------------- COMMAND ---------------- #

class Command(BaseCommand):

    def get_headers(self, token):
        return {
            'Authorization': f'Bearer {token}',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': LI_VERSION,
        }

    def _date_range(self, days=30):
        end = datetime.now()
        start = end - timedelta(days=days)
        return (
            f"(start:(year:{start.year},month:{start.month},day:{start.day}),"
            f"end:(year:{end.year},month:{end.month},day:{end.day}))"
        )

    # ---------- ACCOUNTS ---------- #

    def get_ad_accounts(self, headers):
        res = requests.get(
            'https://api.linkedin.com/rest/adAccounts',
            headers=headers,
            params={'q': 'search'},
        )

        if res.status_code != 200:
            self.stdout.write(self.style.ERROR(res.text))
            return []

        accounts = res.json().get('elements', [])
        self.stdout.write(self.style.SUCCESS(f'✅ Found {len(accounts)} account(s)'))

        for a in accounts:
            self.stdout.write(f"  - {a.get('name')} ({a.get('id')})")

        return accounts

    # ---------- ACCOUNT METRICS ---------- #

    def get_account_analytics(self, headers, account_id, currency):
        symbol = get_currency_symbol(currency)

        params = {
            'q': 'analytics',
            'pivot': 'ACCOUNT',
            'timeGranularity': 'DAILY',
            'dateRange': self._date_range(),
            'accounts': f'List(urn:li:sponsoredAccount:{account_id})',
            'fields': ANALYTICS_FIELDS,
        }

        url = build_analytics_url(params)
        res = requests.get(url, headers=headers)

        elements = res.json().get('elements', [])

        total_imp = sum(e.get('impressions', 0) for e in elements)
        total_clicks = sum(e.get('landingPageClicks', 0) for e in elements)
        total_cost = sum(float(e.get('costInLocalCurrency', 0)) for e in elements)

        ctr = (total_clicks / total_imp * 100) if total_imp else 0
        cpc = (total_cost / total_clicks) if total_clicks else 0
        cpm = (total_cost / total_imp * 1000) if total_imp else 0

        likes = sum(e.get('likes', 0) for e in elements)
        shares = sum(e.get('shares', 0) for e in elements)
        comments = sum(e.get('comments', 0) for e in elements)

        self.stdout.write(self.style.SUCCESS("\n📊 Account Summary"))
        self.stdout.write(
            f"   Spend: {symbol}{total_cost:.2f} | "
            f"Impr: {total_imp:,} | Clicks: {total_clicks} | "
            f"CTR: {ctr:.2f}% | CPC: {symbol}{cpc:.2f} | CPM: {symbol}{cpm:.2f}"
        )
        self.stdout.write(
            f"   Likes: {likes}, Shares: {shares}, Comments: {comments}"
        )

    # ---------- ADS ---------- #

    def get_ads_grouped(self, headers, account_id):
        url = f'https://api.linkedin.com/rest/adAccounts/{account_id}/creatives'
        res = requests.get(url, headers=headers, params={'q': 'criteria', 'count': 100})

        creatives = res.json().get('elements', [])

        campaign_ads = {}
        creative_ids = []

        for ad in creatives:
            cid = ad.get('id')
            if not cid:
                continue

            if isinstance(cid, str) and 'urn:' in cid:
                cid = cid.split(':')[-1]

            campaign = ad.get('campaign')

            campaign_ads.setdefault(campaign, []).append(ad)
            creative_ids.append(cid)

        return campaign_ads, creative_ids

    # ---------- AD ANALYTICS ---------- #

    def get_ad_analytics(self, headers, creative_ids):

        if not creative_ids:
            return {}

        creative_urns = [
            cid if str(cid).startswith('urn:li:sponsoredCreative:')
            else f'urn:li:sponsoredCreative:{cid}'
            for cid in creative_ids
        ]

        params = {
            'q': 'analytics',
            'pivot': 'CREATIVE',
            'timeGranularity': 'MONTHLY',
            'dateRange': self._date_range(),
            'creatives': f'List({",".join(creative_urns)})',
            'fields': ANALYTICS_FIELDS,
        }

        url = build_analytics_url(params)
        res = requests.get(url, headers=headers)

        if res.status_code != 200:
            self.stdout.write(self.style.ERROR(res.text))
            return {}

        elements = res.json().get('elements', [])

        analytics_map = {}

        for e in elements:
            pivot = e.get('pivotValues', [None])[0]

            cost = float(e.get('costInLocalCurrency', 0))
            impressions = e.get('impressions', 0)
            clicks = e.get('landingPageClicks', 0)
            conversions = e.get('externalWebsiteConversions', 0)

            likes = e.get('likes', 0)
            shares = e.get('shares', 0)
            comments = e.get('comments', 0)

            ctr = (clicks / impressions * 100) if impressions else 0
            cpc = (cost / clicks) if clicks else 0
            cpm = (cost / impressions * 1000) if impressions else 0

            analytics_map[pivot] = {
                'cost': cost,
                'impressions': impressions,
                'clicks': clicks,
                'ctr': ctr,
                'cpc': cpc,
                'cpm': cpm,
                'conversions': conversions,
                'likes': likes,
                'shares': shares,
                'comments': comments
            }

        return analytics_map

    # ---------- CAMPAIGNS ---------- #

    def get_campaigns(self, headers, account_id, currency, campaign_ads, ad_metrics):
        symbol = get_currency_symbol(currency)

        res = requests.get(
            f'https://api.linkedin.com/rest/adAccounts/{account_id}/adCampaigns',
            headers=headers,
            params={'q': 'search'}
        )

        campaigns = res.json().get('elements', [])

        for c in campaigns:
            cid = c.get('id')
            name = c.get('name')
            status = c.get('status')

            campaign_urn = f'urn:li:sponsoredCampaign:{cid}'

            self.stdout.write(f"\n📊 {name}")
            self.stdout.write(f"   Status: {status}")

            # Campaign analytics
            params = {
                'q': 'analytics',
                'pivot': 'CAMPAIGN',
                'timeGranularity': 'MONTHLY',
                'dateRange': self._date_range(),
                'campaigns': f'List({campaign_urn})',
                'fields': ANALYTICS_FIELDS,
            }

            url = build_analytics_url(params)
            res = requests.get(url, headers=headers)
            elements = res.json().get('elements', [])

            if elements:
                e = elements[0]

                cost = float(e.get('costInLocalCurrency', 0))
                impressions = e.get('impressions', 0)
                clicks = e.get('landingPageClicks', 0)
                conversions = e.get('externalWebsiteConversions', 0)

                likes = e.get('likes', 0)
                shares = e.get('shares', 0)
                comments = e.get('comments', 0)

                ctr = (clicks / impressions * 100) if impressions else 0
                cpc = (cost / clicks) if clicks else 0
                cpm = (cost / impressions * 1000) if impressions else 0

                self.stdout.write(
                    f"   Spend: {symbol}{cost:.2f} | "
                    f"Impr: {impressions:,} | Clicks: {clicks} | "
                    f"CTR: {ctr:.2f}% | CPC: {symbol}{cpc:.2f} | CPM: {symbol}{cpm:.2f} | "
                    f"Conv: {conversions}"
                )

                self.stdout.write(
                    f"   Likes: {likes}, Shares: {shares}, Comments: {comments}"
                )
            else:
                self.stdout.write("   No data")

            # Ads
            ads = campaign_ads.get(campaign_urn, [])

            if ads:
                self.stdout.write("   Ads:")
                for ad in ads:
                    name = ad.get('name', 'No name')
                    status = ad.get('status') or ad.get('review', {}).get('status', 'Unknown')

                    cid = ad.get('id')
                    if isinstance(cid, str) and 'urn:' in cid:
                        cid = cid.split(':')[-1]

                    creative_urn = f'urn:li:sponsoredCreative:{cid}'
                    metrics = ad_metrics.get(creative_urn, {})

                    self.stdout.write(
                        f"      - {name} ({status}) | "
                        f"Spend: {symbol}{metrics.get('cost', 0):.2f} | "
                        f"Impr: {metrics.get('impressions', 0):,} | "
                        f"Clicks: {metrics.get('clicks', 0)} | "
                        f"CTR: {metrics.get('ctr', 0):.2f}% | "
                        f"CPC: {symbol}{metrics.get('cpc', 0):.2f} | "
                        f"CPM: {symbol}{metrics.get('cpm', 0):.2f} | "
                        f"Conv: {metrics.get('conversions', 0)} | "
                        f"Likes: {metrics.get('likes', 0)}, "
                        f"Shares: {metrics.get('shares', 0)}, "
                        f"Comments: {metrics.get('comments', 0)}"
                    )
            else:
                self.stdout.write("   Ads: None")

    # ---------- MAIN ---------- #

    def handle(self, *args, **kwargs):
        clinic = Clinic.objects.first()

        acc = SocialAccount.objects.filter(
            clinic=clinic,
            platform='linkedin',
            is_active=True
        ).first()

        # headers = self.get_headers(acc.access_token)

        headers = self.get_headers("AQWdXvDdlmpGltJg_XchW3YAZpm9ZjDqFl5tkW-cK9M5xJOHRwfqox7FlPo9z0bRX5zsgO7nYoumZZ8hyGdGQUDFZ0U3O7eZeCSuMsERaWK7NpE4GUY6LnrYlQvtBqsmR07m79_RFfmDqVNW3imepaYsIjLwCMJ5hn1Rb7X3kq1xDsx-CtsIzsTgBtOy7uz0BOJPT7b-Sk8O1aJPEAq8EtKQJ5oAtC8gZy0HpAGtPjWZEUVcGtoJWzTDDM40P3XXoFe9oN7PaeMVhKZYdGt2fScJWsEFucsRvIIfb-zEmAEBikWWoMNu8PGGa-kGKpK5DaHld3sisBewiwogcX3PTCKydBR0KQ")

        accounts = self.get_ad_accounts(headers)

        for a in accounts:
            account_id = a.get('id')
            currency = a.get('currency', 'USD')

            self.stdout.write('\n' + '-' * 60)
            self.stdout.write(f"PROCESSING ACCOUNT: {a.get('name')} ({account_id})")
            self.stdout.write('-' * 60)

            self.get_account_analytics(headers, account_id, currency)

            campaign_ads, creative_ids = self.get_ads_grouped(headers, account_id)
            ad_metrics = self.get_ad_analytics(headers, creative_ids)

            self.get_campaigns(headers, account_id, currency, campaign_ads, ad_metrics)

        self.stdout.write('\n✅ DONE')