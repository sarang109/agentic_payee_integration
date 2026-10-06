### E4c: anchoring against real phishing domains from Kaggle URL datasets

| dataset                                         | trial                                                                    |    n | committed to phishing domain   | committed to genuine brand   | stepped up           |
|:------------------------------------------------|:-------------------------------------------------------------------------|-----:|:-------------------------------|:-----------------------------|:---------------------|
| sid321axn/malicious-urls-dataset                | attack: agent surfaces a real phishing domain resembling the named brand | 4000 | 0.000 [0.000, 0.001]           | 0.644 [0.629, 0.659]         | 0.356 [0.341, 0.371] |
| sid321axn/malicious-urls-dataset                | benign: registry also holds this dataset's legitimate look-alike domains | 2000 | -                              | 0.821 [0.804, 0.837]         | 0.178 [0.162, 0.196] |
| taruntiwarihp/phishing-site-urls                | attack: agent surfaces a real phishing domain resembling the named brand | 4000 | 0.000 [0.000, 0.001]           | 0.677 [0.662, 0.691]         | 0.323 [0.309, 0.338] |
| taruntiwarihp/phishing-site-urls                | benign: registry also holds this dataset's legitimate look-alike domains | 2000 | -                              | 0.817 [0.799, 0.833]         | 0.183 [0.167, 0.201] |
| quangnguynv/phishtank-phishingurl-valid-dataset | attack: agent surfaces a real phishing domain resembling the named brand | 4000 | 0.000 [0.000, 0.001]           | 0.782 [0.769, 0.794]         | 0.218 [0.206, 0.231] |

Same procedure as E4b; no page titles in these datasets. Wilson 95% intervals.
