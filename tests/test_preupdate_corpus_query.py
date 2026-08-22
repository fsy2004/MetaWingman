import unittest
import xml.etree.ElementTree as ET

from metawingman.scripts.build_preupdate_corpus import (
    build_epmc_query,
    build_native_pubmed_query,
    publication_date_from_article,
    pubmed_construct_annotations,
)


class HistoricalWindowQueryTests(unittest.TestCase):
    def test_pubmed_xml_prefers_exact_electronic_article_date(self):
        article = ET.fromstring(
            """<PubmedArticle><MedlineCitation><Article>
            <Journal><JournalIssue><PubDate><Year>2020</Year><Month>Jun</Month></PubDate></JournalIssue></Journal>
            <ArticleDate DateType="Electronic"><Year>2020</Year><Month>06</Month><Day>03</Day></ArticleDate>
            </Article></MedlineCitation></PubmedArticle>"""
        )
        self.assertEqual(publication_date_from_article(article), "2020-06-03")

    def test_pubmed_xml_uses_exact_journal_date_when_article_date_missing(self):
        article = ET.fromstring(
            """<PubmedArticle><MedlineCitation><Article><Journal><JournalIssue>
            <PubDate><Year>2020</Year><Month>May</Month><Day>29</Day></PubDate>
            </JournalIssue></Journal></Article></MedlineCitation></PubmedArticle>"""
        )
        self.assertEqual(publication_date_from_article(article), "2020-05-29")

    def test_pubmed_replaces_embedded_snapshot_date(self):
        source = '("covid"[Text Word]) AND 2019/12/01:2020/12/11[Date - Publication]'
        query = build_native_pubmed_query(source, "2019-12-01", "2021-08-31")
        self.assertIn('2019/12/01:2021/08/31[Date - Publication]', query)
        self.assertNotIn('2020/12/11', query)
        self.assertEqual(query.count('[Date - Publication]'), 1)

    def test_epmc_replaces_embedded_snapshot_date(self):
        source = '(covid) AND FIRST_PDATE:[2019-12-01 TO 2020-12-11]'
        query = build_epmc_query(source, "2019-12-01", "2021-08-31")
        self.assertIn('FIRST_PDATE:[2019-12-01 TO 2021-08-31]', query)
        self.assertNotIn('2020-12-11', query)
        self.assertEqual(query.count('FIRST_PDATE:'), 1)

    def test_concept_terms_are_not_rewritten(self):
        source = '("rapid test*"[Text Word] OR "RDT"[Text Word]) AND 2019/12/01:2020/12/11[Date - Publication]'
        query = build_native_pubmed_query(source, "2021-05-01", "2021-08-31")
        self.assertIn('"rapid test*"[Text Word] OR "RDT"[Text Word]', query)
        self.assertIn('2021/05/01:2021/08/31[Date - Publication]', query)

    def test_pubmed_construct_annotations_preserve_explicit_mesh_registry_and_guideline_evidence(self):
        article = ET.fromstring(
            """<PubmedArticle><MedlineCitation>
            <Article><ArticleTitle>Clinical guideline for depression</ArticleTitle>
              <PublicationTypeList><PublicationType>Practice Guideline</PublicationType></PublicationTypeList>
              <DataBankList><DataBank><DataBankName>ClinicalTrials.gov</DataBankName>
                <AccessionNumberList><AccessionNumber>NCT01234567</AccessionNumber></AccessionNumberList>
              </DataBank></DataBankList>
            </Article>
            <MeshHeadingList>
              <MeshHeading><DescriptorName UI="D003863">Depression</DescriptorName></MeshHeading>
              <MeshHeading><DescriptorName UI="D006801">Humans</DescriptorName></MeshHeading>
            </MeshHeadingList>
            </MedlineCitation></PubmedArticle>"""
        )
        self.assertEqual(pubmed_construct_annotations(article), {
            "mesh_terms": ["Depression", "Humans"],
            "publication_types": ["Practice Guideline"],
            "registry_ids": ["NCT01234567"],
            "study_family_ids": ["NCT01234567"],
            "decision_anchor_type": "guideline",
            "construct_annotation_basis": "explicit_pubmed_xml_v1",
        })

    def test_nonanchor_without_registry_does_not_invent_family_or_decision_relevance(self):
        article = ET.fromstring(
            """<PubmedArticle><MedlineCitation><Article>
              <ArticleTitle>A cohort report</ArticleTitle>
              <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
            </Article></MedlineCitation></PubmedArticle>"""
        )
        annotations = pubmed_construct_annotations(article)
        self.assertNotIn("decision_anchor_type", annotations)
        self.assertEqual(annotations["study_family_ids"], [])


if __name__ == "__main__":
    unittest.main()
