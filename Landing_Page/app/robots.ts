import type { MetadataRoute } from "next";
import { PRODUCT } from "@/lib/product";

export const dynamic = "force-static";
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${PRODUCT.origin}/sitemap.xml`,
  };
}
