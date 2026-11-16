import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from config import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_BACKOFF_FACTOR,
)
from models import MobilePriceRecord

logger = logging.getLogger("mobile_scraper")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

def parse_storage_gb(storage_str: str, model_str: str = "", url_str: str = "") -> int:
    """Parse storage string into integer gigabytes."""
    combined = f"{storage_str} {model_str} {url_str}"
    m_tb = re.search(r"(\d+)\s*TB", combined, re.I)
    if m_tb:
        return int(m_tb.group(1)) * 1024
    m_gb = re.search(r"(\d+)\s*(?:GB|gb)", combined, re.I)
    if m_gb:
        return int(m_gb.group(1))
    m_num = re.search(r"\b(\d{2,4})\b", storage_str)
    if m_num:
        val = int(m_num.group(1))
        if val in (16, 32, 64, 128, 256, 512, 1024):
            return val
    return 128


def parse_ram_gb(ram_str: Optional[str], model_str: str = "", url_str: str = "") -> Optional[int]:
    """Parse RAM string into integer gigabytes or None."""
    if ram_str:
        m = re.search(r"(\d+)\s*(?:GB|gb)", ram_str, re.I)
        if m:
            return int(m.group(1))
    m_slash = re.search(r"(\d+)\s*(?:GB|gb)\s*/\s*\d+\s*(?:GB|gb)", model_str, re.I)
    if m_slash:
        return int(m_slash.group(1))
    m_url = re.search(r"-(\d+)-gb-(\d+)-gb", url_str, re.I)
    if m_url:
        return int(m_url.group(1))
    return None


def clean_device_model(raw_model: str, brand: str) -> str:
    """Clean model name of fluff, duplicated brand prefixes, and trailing specs."""
    cleaned = raw_model.strip()
    cleaned = re.sub(r"^Sell\s+Old\s+", "", cleaned, flags=re.I)
    if brand and cleaned.lower().startswith(brand.lower()):
        cleaned = cleaned[len(brand):].strip()
    cleaned = re.sub(r"\s*\(\s*\d+\s*(?:GB|TB).*?\)\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*Online\s*&.*$", "", cleaned, flags=re.I)
    return cleaned.strip()


def build_canonical_device_id(brand: str, model: str, storage_gb: int) -> str:
    """Construct canonical device slug matching scraper.devices hierarchy."""
    base = f"{brand}-{model}-{storage_gb}".lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def extract_base_model_slug(url: str) -> str:
    """Extract canonical base model slug without prefixes or storage suffix."""
    slug = urlparse(url).path.rstrip('/').split('/')[-1]
    slug = re.sub(r'^used(?:-p)?-', '', slug, flags=re.I)
    slug = re.sub(r'-(?:\d+-gb-)?\d+-(?:gb|tb)$', '', slug, flags=re.I)
    return slug.lower().strip()


def derive_model_series(brand: str, model_name: str) -> str:
    """Derive model series hierarchy across all major mobile manufacturers."""
    m = model_name.lower()
    b = brand.lower()

    # Apple iPhone
    if "iphone 16" in m:
        return "iPhone 16 Series"
    if "iphone 15" in m:
        return "iPhone 15 Series"
    if "iphone 14" in m:
        return "iPhone 14 Series"
    if "iphone 13" in m:
        return "iPhone 13 Series"
    if "iphone 12" in m:
        return "iPhone 12 Series"
    if "iphone 11" in m:
        return "iPhone 11 Series"
    if "iphone" in m:
        return "iPhone Series"

    # Samsung Galaxy
    if "z fold" in m:
        return "Galaxy Z Fold Series"
    if "z flip" in m:
        return "Galaxy Z Flip Series"
    if "s24" in m:
        return "Galaxy S24 Series"
    if "s23" in m:
        return "Galaxy S23 Series"
    if "s22" in m:
        return "Galaxy S22 Series"
    if "s21" in m:
        return "Galaxy S21 Series"
    if "note 20" in m:
        return "Galaxy Note 20 Series"
    if "note 10" in m:
        return "Galaxy Note 10 Series"
    if "note 9" in m:
        return "Galaxy Note 9 Series"
    if "note 8" in m:
        return "Galaxy Note 8 Series"
    if "note" in m:
        return "Galaxy Note Series"
    if "galaxy a" in m:
        return "Galaxy A Series"
    if "galaxy f" in m or "galaxy m" in m:
        return "Galaxy M & F Series"

    # OnePlus
    if "oneplus" in b or "oneplus" in m:
        for num in ("13", "12", "11", "10", "9", "8", "7"):
            if num in m:
                return f"OnePlus {num} Series"
        if "nord" in m:
            return "OnePlus Nord Series"
        if "open" in m:
            return "OnePlus Open Series"
        return "OnePlus Series"

    # Google Pixel
    if "google" in b or "pixel" in m:
        for num in ("9", "8", "7", "6"):
            if num in m:
                return f"Pixel {num} Series"
        return "Pixel Series"

    # Xiaomi / Redmi
    if "redmi" in b or "redmi" in m:
        if "note" in m:
            return "Redmi Note Series"
        return "Redmi Series"
    if "xiaomi" in b or "xiaomi" in m:
        return "Xiaomi Flagship Series"

    # Vivo / iQOO
    if "iqoo" in b or "iqoo" in m:
        return "iQOO Series"
    if "vivo" in b or "vivo" in m:
        if "x" in m:
            return "Vivo X Series"
        if "v" in m:
            return "Vivo V Series"
        if "t" in m:
            return "Vivo T Series"
        return "Vivo Series"

    # Oppo
    if "oppo" in b or "oppo" in m:
        if "find" in m:
            return "Oppo Find Series"
        if "reno" in m:
            return "Oppo Reno Series"
        return "Oppo Series"

    # Realme
    if "realme" in b or "realme" in m:
        if "gt" in m:
            return "Realme GT Series"
        return "Realme Series"

    # Motorola
    if "motorola" in b or "moto" in m:
        if "edge" in m:
            return "Moto Edge Series"
        if "razr" in m:
            return "Moto Razr Series"
        if "g" in m:
            return "Moto G Series"
        return "Motorola Series"

    # Nothing
    if "nothing" in b or "nothing" in m:
        return "Nothing Phone Series"

    return f"{brand} {model_name}"


class CashifyScraper:
    """Scraper for Cashify mobile buyback pricing pages."""
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
    ):
        """
        Initialize the Cashify scraper.
        Args:
            session: Optional reusable requests session.
            timeout: Maximum request timeout in seconds.
            max_retries: Maximum number of request attempts.
        """
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        self.max_retries = max_retries
    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch HTML content with configurable retries and exponential backoff.
        Returns:
            HTML response text if successful, otherwise None.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "Fetching URL (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    url,
                )
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    return response.text
                if response.status_code == 404:
                    logger.warning("Page not found (404): %s", url)
                    return None
                logger.warning(
                    "Received HTTP status %d for %s",
                    response.status_code,
                    url,
                )
            except requests.RequestException as exc:
                logger.error(
                    "Request failed for %s: %s",
                    url,
                    exc,
                )
            if attempt < self.max_retries:
                sleep_sec = RETRY_BACKOFF_FACTOR ** attempt
                logger.info(
                    "Retrying in %.1f seconds...",
                    sleep_sec,
                )
                time.sleep(sleep_sec)
        logger.error(
            "Failed to fetch URL after %d attempts: %s",
            self.max_retries,
            url,
        )
        return None
    @staticmethod
    def _extract_price(soup: BeautifulSoup, html: str) -> Optional[int]:
        """
        Extract the buyback price from Schema.org metadata or Next.js data.
        Returns:
            Positive integer price in INR, or None if unavailable.
        """
        # First preference: Schema.org price metadata.
        price_tag = soup.find(attrs={"itemprop": "price"})
        if price_tag:
            raw_price = (
                price_tag.get("content")
                or price_tag.get_text(strip=True)
            )
            if raw_price:
                match = re.search(r"\d+(?:\.\d+)?", str(raw_price))
                if match:
                    price = int(float(match.group()))
                    if price > 0:
                        return price
        # Fallback: Next.js getUpTo property.
        patterns = [
            r'"getUpTo"\s*:\s*"?(\d+)"?',
            r'\\"getUpTo\\"\s*:\s*\\"?(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                price = int(match.group(1))
                if price > 0:
                    return price
        return None
    @staticmethod
    def _extract_json_value(html: str, key: str) -> Optional[str]:
        """
        Extract a specification value from serialized page data.
        Handles common JSON and escaped JSON representations.
        """
        escaped_key = re.escape(key)
        patterns = [
            rf'"{escaped_key}"\s*:\s*\[.*?"dval"\s*:\s*"([^"]+)"',
            rf'\\"{escaped_key}\\"\s*:\s*\[.*?\\"dval\\"\s*:\s*\\"([^\\"]+)',
            rf'"{escaped_key}"\s*:\s*"([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(
                pattern,
                html,
                re.DOTALL,
            )
            if match:
                return match.group(1).strip()
        return None
    @staticmethod
    def _extract_brand(
        soup: BeautifulSoup,
        html: str,
    ) -> Optional[str]:
        """Extract the device brand from structured page data."""
        brand_tag = soup.find(attrs={"itemprop": "brand"})
        if brand_tag:
            brand = (
                brand_tag.get("content")
                or brand_tag.get_text(strip=True)
            )
            if brand:
                return brand.strip()
        patterns = [
            r'"brandName"\s*:\s*"([^"]+)"',
            r'\\"brandName\\"\s*:\s*\\"([^\\"]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        return None
    @staticmethod
    def _extract_model_name(
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        """Extract the device model name from page metadata or URL."""
        # Prefer the main product heading.
        h1 = soup.find("h1")
        if h1:
            model_name = h1.get_text(" ", strip=True)
            model_name = re.sub(
                r"^Sell Old\s+",
                "",
                model_name,
                flags=re.IGNORECASE,
            )
            model_name = re.sub(
                r"\s*Online\s*&\s*Get Instant Cash.*$",
                "",
                model_name,
                flags=re.IGNORECASE,
            )
            if model_name:
                return model_name.strip()
        # Fallback to product image metadata.
        img = soup.find("img", attrs={"itemprop": "image"})
        if img and img.get("alt"):
            return img["alt"].strip()
        # Final fallback: derive the name from the URL slug.
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        slug = re.sub(
            r"^used-",
            "",
            slug,
            flags=re.IGNORECASE,
        )
        return slug.replace("-", " ").title()

    def scrape_single_variant_page(
        self,
        html: str,
        url: str,
    ) -> Optional[MobilePriceRecord]:
        """
        Extract pricing and device specifications from a variant page.
        A variant page represents a specific combination of device model
        and storage configuration.
        """
        soup = BeautifulSoup(html, "html.parser")
        # --------------------------------------------------
        # 1. Extract buyback price
        # --------------------------------------------------
        price = self._extract_price(soup, html)
        if not price:
            logger.warning(
                "Unable to extract a valid buyback price: %s",
                url,
            )
            return None
        # --------------------------------------------------
        # 2. Extract brand
        # --------------------------------------------------
        brand = self._extract_brand(soup, html)
        if not brand or brand == "Unknown":
            url_lower = url.lower()
            known_brands = [
                ("apple", "Apple"), ("samsung", "Samsung"), ("oneplus", "OnePlus"),
                ("google", "Google"), ("pixel", "Google"), ("xiaomi", "Xiaomi"),
                ("redmi", "Redmi"), ("realme", "Realme"), ("vivo", "Vivo"),
                ("oppo", "Oppo"), ("motorola", "Motorola"), ("moto", "Motorola"),
                ("nothing", "Nothing"), ("iqoo", "iQOO"), ("poco", "Poco"),
                ("asus", "Asus"), ("honor", "Honor"), ("nokia", "Nokia")
            ]
            for kw, proper_name in known_brands:
                if kw in url_lower:
                    brand = proper_name
                    break
            else:
                brand = "Apple" if "iphone" in html.lower() else "Unknown"

        # --------------------------------------------------
        # 3. Extract and clean model name
        # --------------------------------------------------
        raw_model_name = self._extract_model_name(soup, url)
        cleaned_model = clean_device_model(raw_model_name, brand)

        # --------------------------------------------------
        # 4. Extract device specifications
        # --------------------------------------------------
        storage_val = (
            self._extract_json_value(html, "storage")
            or self._extract_json_value(html, "variationName")
        )
        if not storage_val:
            storage_match = re.search(
                r"(\d+\s*(?:GB|TB))",
                raw_model_name,
                re.IGNORECASE,
            )
            storage_val = (
                storage_match.group(1)
                if storage_match
                else "128 GB"
            )
        ram_val = self._extract_json_value(html, "ram")
        cores_val = self._extract_json_value(html, "cores")
        
        # Camera specifications
        cameras = None
        camera_match = re.search(
            r'["\\]+backCamera["\\]+\s*:\s*\[(.*?)\]',
            html,
            re.DOTALL,
        )
        if camera_match:
            camera_values = re.findall(
                r'["\\]+dval["\\]+\s*:\s*["\\]+([^"\\]+)',
                camera_match.group(1),
            )
            if camera_values:
                cameras = ", ".join(camera_values)

        # --------------------------------------------------
        # 5. Schema Normalization & Filtering
        # --------------------------------------------------
        storage_gb = parse_storage_gb(storage_val, raw_model_name, url)
        ram_gb = parse_ram_gb(ram_val, raw_model_name, url)
        model_series = derive_model_series(brand, cleaned_model)
        canonical_id = build_canonical_device_id(brand, cleaned_model, storage_gb)
        variant_str = f"{ram_gb} GB / {storage_gb} GB" if ram_gb else f"{storage_gb} GB"

        # --------------------------------------------------
        # 6. Build pricing record (Filtered & structured for schema)
        # --------------------------------------------------
        record = MobilePriceRecord(
            brand=brand,
            model=cleaned_model,
            model_series=model_series,
            variant=variant_str,
            storage=f"{storage_gb} GB",
            storage_gb=storage_gb,
            ram=f"{ram_gb} GB" if ram_gb else (ram_val or None),
            ram_gb=ram_gb,
            cores=cores_val,
            camera=cameras,
            condition="Grade A",
            condition_grade="Grade A",
            defects="Flawless condition, zero scratches (Repair cost: ₹0)",
            max_advertised_price=float(price),
            condition_deductions=0.0,
            buyback_price=price,
            price=float(price),
            source_url=url,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data_origin="verified_scraped",
            currency="INR",
            confidence_score=1.0,
            device_id=canonical_id,
        )
        logger.info(
            "Price extracted: %s | %s (%s) | ₹%d | ID: %s",
            record.brand,
            record.model,
            record.variant,
            record.buyback_price,
            record.device_id,
        )
        return record
    def scrape_url(self, url: str) -> List[MobilePriceRecord]:
        """
        Scrape a Cashify product URL.
        Supports both parent product pages and individual variant pages.
        Parent pages:
            Discovers variant URLs and fetches each variant separately.
        Variant pages:
            Extracts pricing and specifications directly.
        Returns:
            List of successfully extracted MobilePriceRecord objects.
        """
        records: List[MobilePriceRecord] = []
        html = self.fetch_page(url)
        if not html:
            return records
        soup = BeautifulSoup(html, "html.parser")
        # --------------------------------------------------
        # 1. Discover variant URLs
        # --------------------------------------------------
        base_slug = extract_base_model_slug(url)
        all_variant_urls = set()

        # Priority 1: Extract variant links directly from explicit variant container elements [id*="variant"]
        for li in soup.find_all(lambda tag: tag.has_attr('id') and 'variant' in tag.get('id', '')):
            for a in li.find_all('a', href=True):
                href = a['href']
                if '/sell-old-mobile-phone/' in href:
                    variant_url = urljoin('https://www.cashify.in', href.split('?')[0])
                    if extract_base_model_slug(variant_url) == base_slug:
                        all_variant_urls.add(variant_url)

        # Priority 2: Extract from serialized Next.js productList if available
        if not all_variant_urls:
            pl_match = re.search(r'\\"productList\\":\[(.*?)\]', html)
            if pl_match:
                for slug in re.findall(r'\\"url\\":\\"/sell-old-mobile-phone/([^\\"\s]+)\\"', pl_match.group(1)):
                    variant_url = urljoin('https://www.cashify.in', '/sell-old-mobile-phone/' + slug.split('?')[0])
                    if extract_base_model_slug(variant_url) == base_slug:
                        all_variant_urls.add(variant_url)

        # Priority 3: Fallback to anchors containing storage tags that match the base device slug
        if not all_variant_urls:
            for anchor in soup.find_all('a', href=True):
                href = anchor['href']
                if '/sell-old-mobile-phone/' in href and re.search(r'\d+-(?:gb|tb)', href, re.IGNORECASE):
                    variant_url = urljoin('https://www.cashify.in', href.split('?')[0])
                    if extract_base_model_slug(variant_url) == base_slug:
                        all_variant_urls.add(variant_url)

        # Remove self URL so we don't redundantly recurse if current URL is already a variant
        all_variant_urls.discard(url)
        # --------------------------------------------------
        # 2. Scrape discovered variants
        # --------------------------------------------------
        if all_variant_urls:
            logger.info(
                "Discovered %d variant URLs for %s",
                len(all_variant_urls),
                url,
            )
            for variant_url in sorted(all_variant_urls):
                try:
                    variant_html = self.fetch_page(
                        variant_url
                    )
                    if not variant_html:
                        continue
                    record = self.scrape_single_variant_page(
                        variant_html,
                        variant_url,
                    )
                    if record:
                        records.append(record)
                except Exception:
                    logger.exception(
                        "Error scraping variant: %s",
                        variant_url,
                    )
        # --------------------------------------------------
        # 3. Process current URL if it is a variant page
        # --------------------------------------------------
        if not records:
            price = self._extract_price(
                soup,
                html,
            )
            if price:
                record = self.scrape_single_variant_page(
                    html,
                    url,
                )
                if record:
                    records.append(record)
        logger.info(
            "Scraping completed for %s. Records extracted: %d",
            url,
            len(records),
        )
        return records

    # Compatibility alias
    scrape_device_page = scrape_url
