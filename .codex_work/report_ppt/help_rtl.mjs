import { Presentation } from "@oai/artifact-tool";

const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
for (const search of ["rtl|bidi|rightToLeft|readingOrder", "paragraph direction arabic hebrew"]) {
  const result = presentation.help("*", {
    search,
    include: ["index", "examples", "notes"],
    maxChars: 12000,
  });
  console.log(`SEARCH=${search}`);
  console.log(result.ndjson);
}
