-- Add structured university policy/ranking tags to institutions.
--
-- Sources:
-- - QS World University Rankings 2026, TopUniversities/QS public ranking page
-- - 985/211 project public university lists
-- - Ministry of Education second-round Double First-Class university list

ALTER TABLE institutions
  ADD COLUMN IF NOT EXISTS is_985 BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_211 BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_double_first_class BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS qs_rank INTEGER NULL,
  ADD COLUMN IF NOT EXISTS qs_rank_band VARCHAR(16) NULL;

CREATE INDEX IF NOT EXISTS idx_institutions_is_985
  ON institutions (is_985)
  WHERE entity_type = 'organization';

CREATE INDEX IF NOT EXISTS idx_institutions_is_211
  ON institutions (is_211)
  WHERE entity_type = 'organization';

CREATE INDEX IF NOT EXISTS idx_institutions_is_double_first_class
  ON institutions (is_double_first_class)
  WHERE entity_type = 'organization';

CREATE INDEX IF NOT EXISTS idx_institutions_qs_rank_band
  ON institutions (qs_rank_band)
  WHERE entity_type = 'organization';

UPDATE institutions
SET is_985 = true
WHERE entity_type = 'organization'
  AND name IN (
    '北京大学', '清华大学', '中国人民大学', '北京航空航天大学', '北京理工大学',
    '北京师范大学', '中国农业大学', '中央民族大学', '复旦大学', '上海交通大学',
    '同济大学', '华东师范大学', '南京大学', '东南大学', '浙江大学',
    '中国科学技术大学', '厦门大学', '山东大学', '中国海洋大学', '武汉大学',
    '华中科技大学', '中南大学', '湖南大学', '中山大学', '华南理工大学',
    '四川大学', '电子科技大学', '重庆大学', '西安交通大学', '西北工业大学',
    '西北农林科技大学', '兰州大学', '南开大学', '天津大学', '大连理工大学',
    '东北大学', '吉林大学', '哈尔滨工业大学', '国防科技大学'
  );

UPDATE institutions
SET is_211 = true
WHERE entity_type = 'organization'
  AND name IN (
    '北京大学', '清华大学', '中国人民大学', '北京交通大学', '北京工业大学',
    '北京航空航天大学', '北京理工大学', '北京科技大学', '北京化工大学',
    '北京邮电大学', '中国农业大学', '北京林业大学', '北京中医药大学',
    '北京师范大学', '北京外国语大学', '中国传媒大学', '中央财经大学',
    '对外经济贸易大学', '北京体育大学', '中央音乐学院', '中央民族大学',
    '中国政法大学', '华北电力大学', '中国矿业大学', '中国石油大学',
    '中国地质大学', '南开大学', '天津大学', '天津医科大学', '河北工业大学',
    '太原理工大学', '内蒙古大学', '大连理工大学', '东北大学', '辽宁大学',
    '大连海事大学', '吉林大学', '东北师范大学', '延边大学', '哈尔滨工业大学',
    '哈尔滨工程大学', '东北农业大学', '东北林业大学', '复旦大学', '同济大学',
    '上海交通大学', '华东理工大学', '东华大学', '华东师范大学', '上海外国语大学',
    '上海财经大学', '上海大学', '南京大学', '苏州大学', '东南大学',
    '南京航空航天大学', '南京理工大学', '中国矿业大学', '河海大学', '江南大学',
    '南京农业大学', '中国药科大学', '南京师范大学', '浙江大学',
    '中国科学技术大学', '安徽大学', '合肥工业大学', '厦门大学', '福州大学',
    '南昌大学', '山东大学', '中国海洋大学', '中国石油大学', '郑州大学',
    '武汉大学', '华中科技大学', '中国地质大学', '武汉理工大学', '华中师范大学',
    '华中农业大学', '中南财经政法大学', '湖南大学', '中南大学', '湖南师范大学',
    '中山大学', '暨南大学', '华南理工大学', '华南师范大学', '广西大学',
    '海南大学', '四川大学', '西南交通大学', '电子科技大学', '四川农业大学',
    '西南财经大学', '重庆大学', '西南大学', '贵州大学', '云南大学', '西藏大学',
    '西北大学', '西安交通大学', '西北工业大学', '西安电子科技大学', '长安大学',
    '西北农林科技大学', '陕西师范大学', '兰州大学', '青海大学', '宁夏大学',
    '新疆大学', '石河子大学', '国防科技大学'
  );

UPDATE institutions
SET is_double_first_class = true
WHERE entity_type = 'organization'
  AND (
    is_211 = true
    OR name IN (
      '北京协和医学院', '中国科学院大学', '首都师范大学', '外交学院',
      '中国人民公安大学', '中国音乐学院', '中央美术学院', '中央戏剧学院',
      '天津工业大学', '天津中医药大学', '山西大学', '上海中医药大学',
      '上海海洋大学', '上海体育学院', '上海音乐学院', '南京邮电大学',
      '南京信息工程大学', '南京林业大学', '南京医科大学', '南京中医药大学',
      '中国美术学院', '宁波大学', '河南大学', '湘潭大学', '广州医科大学',
      '广州中医药大学', '南方科技大学', '成都理工大学', '西南石油大学',
      '成都中医药大学'
    )
  );

WITH qs_rankings(name, qs_rank) AS (
  VALUES
    ('Imperial College London', 2), ('伦敦帝国学院', 2), ('伦敦帝国理工学院', 2),
    ('帝国理工学院', 2),
    ('Stanford University', 3), ('斯坦福大学', 3),
    ('University of Oxford', 4), ('牛津大学', 4),
    ('Harvard University', 5), ('哈佛大学', 5),
    ('University of Cambridge', 6), ('剑桥大学', 6),
    ('ETH Zurich', 7), ('苏黎世联邦理工学院', 7),
    ('National University of Singapore', 8), ('National University of Singapore (NUS)', 8),
    ('新加坡国立大学', 8), ('新加坡国立', 8),
    ('UCL', 9), ('伦敦大学学院', 9),
    ('California Institute of Technology (Caltech)', 10), ('加州理工学院', 10),
    ('The University of Hong Kong', 11), ('香港大学', 11),
    ('Nanyang Technological University, Singapore (NTU Singapore)', 12),
    ('南洋理工大学', 12), ('南洋理工', 12),
    ('University of Chicago', 13), ('芝加哥大学', 13),
    ('Peking University', 14), ('北京大学', 14),
    ('University of Pennsylvania', 15), ('宾夕法尼亚大学', 15),
    ('Cornell University', 16), ('康奈尔大学', 16),
    ('Tsinghua University', 17), ('清华大学', 17),
    ('University of California, Berkeley (UCB)', 17), ('加利福尼亚大学伯克利分校', 17),
    ('The University of Melbourne', 19), ('墨尔本大学', 19),
    ('The University of New South Wales (UNSW Sydney)', 20),
    ('Yale University', 21), ('耶鲁大学', 21),
    ('EPFL – École polytechnique fédérale de Lausanne', 22), ('洛桑联邦理工学院', 22),
    ('Technical University of Munich', 22), ('慕尼黑工业大学', 22),
    ('Johns Hopkins University', 24), ('约翰斯·霍普金斯大学', 24), ('约翰斯霍普金斯大学', 24),
    ('Princeton University', 25), ('普林斯顿大学', 25),
    ('The University of Sydney', 25), ('悉尼大学', 25),
    ('University of Toronto', 29), ('多伦多大学', 29),
    ('Fudan University', 30), ('复旦大学', 30),
    ('King''s College London', 31), ('伦敦国王学院', 31),
    ('Australian National University (ANU)', 32), ('Australian National University', 32),
    ('澳大利亚国立大学', 32),
    ('The University of Edinburgh', 34), ('University of Edinburgh', 34), ('爱丁堡大学', 34),
    ('The University of Manchester', 35), ('曼彻斯特大学', 35),
    ('Monash University', 36), ('莫纳什大学', 36), ('澳大利亚莫纳什大学', 36),
    ('The University of Tokyo', 36), ('东京大学', 36),
    ('Columbia University', 38), ('哥伦比亚大学', 38),
    ('University of British Columbia', 40), ('不列颠哥伦比亚大学', 40),
    ('Northwestern University', 42),
    ('The University of Queensland', 42), ('University of Queensland', 42), ('昆士兰大学', 42),
    ('The Hong Kong University of Science and Technology', 44),
    ('University of Michigan-Ann Arbor', 45), ('密歇根大学安娜堡分校', 45),
    ('University of California, Los Angeles (UCLA)', 46),
    ('Delft University of Technology', 47), ('代尔夫特理工大学', 47),
    ('Shanghai Jiao Tong University', 47), ('上海交通大学', 47),
    ('Zhejiang University', 49), ('浙江大学', 49),
    ('Carnegie Mellon University', 52), ('卡内基梅隆大学', 52),
    ('New York University (NYU)', 55), ('New York University', 55), ('纽约大学', 55),
    ('University of Texas at Austin', 68), ('德克萨斯大学奥斯汀分校', 68),
    ('University of Illinois Urbana-Champaign', 70), ('University of Illinois at Urbana-Champaign', 70),
    ('University of Warwick', 74), ('华威大学', 74),
    ('University of Birmingham', 76), ('伯明翰大学', 76),
    ('KTH Royal Institute of Technology', 78), ('瑞典皇家理工学院', 78),
    ('University of Washington', 81), ('华盛顿大学', 81),
    ('Adelaide University', 82), ('University of Adelaide', 82), ('阿德莱德大学', 82),
    ('Pennsylvania State University', 82), ('宾夕法尼亚州立大学', 82),
    ('Tokyo Institute of Technology (Tokyo Tech)', 85), ('东京工业大学', 85),
    ('Boston University', 88), ('波士顿大学', 88),
    ('University of Alberta', 94), ('University of Technology Sydney', 96), ('悉尼科技大学', 96),
    ('KIT, Karlsruhe Institute of Technology', 98), ('卡尔斯鲁厄理工学院', 98),
    ('Politecnico di Milano', 98), ('米兰理工大学', 98),
    ('University of Copenhagen', 101), ('哥本哈根大学', 101),
    ('Nanjing University', 103), ('南京大学', 103),
    ('RWTH Aachen University', 105), ('亚琛工业大学', 105),
    ('Rice University', 119), ('莱斯大学', 119),
    ('University of Waterloo', 119), ('滑铁卢大学', 119),
    ('Georgia Institute of Technology', 123), ('佐治亚理工学院', 123),
    ('Indian Institute of Technology Delhi (IITD)', 123), ('印度理工学院', 123),
    ('RMIT University', 125),
    ('Aarhus University', 131), ('奥尔胡斯大学', 131),
    ('University of Science and Technology of China', 132), ('中国科学技术大学', 132),
    ('Newcastle University', 137), ('纽卡斯尔大学', 137),
    ('Alma Mater Studiorum - Università di Bologna', 138), ('博洛尼亚大学', 138),
    ('Eindhoven University of Technology', 140), ('埃因霍温理工大学', 140),
    ('Texas A&M University', 144), ('德州农工大学', 144),
    ('Technische Universität Berlin (TU Berlin)', 145), ('柏林工业大学', 145),
    ('University of Southern California', 147), ('南加州大学', 147),
    ('University of Groningen', 147), ('格罗宁根大学', 147),
    ('University of Liverpool', 150), ('利物浦大学', 150),
    ('University of Exeter', 155), ('埃克塞特大学', 155),
    ('Michigan State University', 162), ('密歇根州立大学', 162),
    ('Ghent University', 163), ('比利时根特大学', 163),
    ('Washington University in St. Louis', 168), ('圣路易斯华盛顿大学', 168),
    ('Université de Montréal', 169), ('University of Montreal', 169), ('蒙特利尔大学', 169),
    ('Hokkaido University', 170), ('北海道大学', 170),
    ('Tongji University', 177), ('同济大学', 177),
    ('Cardiff University', 182), ('Cardiff University', 182), ('卡迪夫大学', 182), ('英国卡迪夫大学', 182),
    ('Emory University', 183), ('埃默里大学', 183),
    ('Wuhan University', 186), ('武汉大学', 186),
    ('The Ohio State University', 190), ('Ohio State University', 190), ('俄亥俄州立大学', 190),
    ('Waseda University', 197), ('早稻田大学', 197),
    ('National Yang Ming Chiao Tung University (NYCU)', 199), ('国立阳明交通大学', 199),
    ('Queen''s University Belfast', 199), ('Queen’s University Belfast', 199)
)
UPDATE institutions AS i
SET
  qs_rank = q.qs_rank,
  qs_rank_band = CASE
    WHEN q.qs_rank <= 30 THEN '前30'
    WHEN q.qs_rank <= 50 THEN '前50'
    WHEN q.qs_rank <= 100 THEN '前100'
    WHEN q.qs_rank <= 200 THEN '前200'
    ELSE '200外'
  END
FROM qs_rankings AS q
WHERE i.entity_type = 'organization'
  AND (i.name = q.name OR i.org_name = q.name);

UPDATE institutions
SET qs_rank_band = '200外'
WHERE entity_type = 'organization'
  AND org_type = '高校'
  AND qs_rank IS NULL
  AND qs_rank_band IS NULL;
