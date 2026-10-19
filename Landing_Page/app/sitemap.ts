import type { MetadataRoute } from "next";
import { PRODUCT } from "@/lib/product";

export const dynamic = "force-static";
export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "features/", "how-it-works/", "download/", "privacy/"].map(route => ({
    url: `${PRODUCT.origin}/${route}`,
  }));
}
