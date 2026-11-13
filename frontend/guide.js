'use strict';
// Small, code-native diagrams: the guide explains concepts without an external image service.
window.LoopGuide = (() => {
  const find = id => document.getElementById(id);
  const concepts = {
    ai: {topic:3,title:'신경망 구조',description:'신경망은 입력 특징을 여러 층에서 변환해 예측을 만듭니다.',points:['입력층: 데이터의 특징을 받습니다.','은닉층: 가중치와 활성화 함수로 특징을 변환합니다.','출력층: 문제에 맞는 예측을 만듭니다.'],type:'network'},
    ml: {topic:3,title:'학습과 일반화',description:'훈련 데이터에서 배운 패턴이 새로운 데이터에서도 잘 작동해야 합니다.',points:['훈련 데이터는 모델의 가중치를 학습하는 데 사용합니다.','검증 데이터로 설정을 비교합니다.','테스트 데이터는 최종 평가를 위해 분리합니다.'],type:'dataset'},
    data: {topic:3,title:'데이터 나누기',description:'학습·검증·테스트 데이터를 분리하면 새로운 데이터에 대한 성능을 더 공정하게 확인할 수 있습니다.',points:['분할 비율은 예시이며 데이터와 과제에 따라 조정합니다.','평가 데이터의 정보가 학습에 섞이지 않게 합니다.'],type:'dataset'},
    evaluation: {topic:3,title:'모델 평가',description:'정밀도는 양성 예측 중 맞힌 비율, 재현율은 실제 양성 중 찾아낸 비율입니다.',points:['정밀도 = TP / (TP + FP)','재현율 = TP / (TP + FN)','F1은 정밀도와 재현율의 조화평균입니다.'],type:'evaluation'},
    python: {topic:2,title:'리스트와 인덱스',description:'리스트는 여러 값을 순서대로 보관합니다. 인덱스는 0부터 시작하고 append로 값을 추가할 수 있습니다.',points:['items[0]은 첫 번째 값인 10입니다.','items.append(40)은 맨 뒤에 40을 추가합니다.'],type:'list'},
    sql: {topic:1,title:'기본키와 외래키',description:'기본키는 행을 고유하게 식별하고, 외래키는 서로 다른 테이블의 관계를 연결합니다.',points:['학생 한 명은 여러 수강 기록을 가질 수 있습니다.','수강 테이블의 학생번호는 학생 테이블을 참조합니다.'],type:'schema'},
  };
  let current = 'ai';
  function node(tag, className, text) { const value=document.createElement(tag); if(className)value.className=className;if(text!==undefined)value.textContent=text;return value; }
  function svgNode(tag, attributes, text) { const value=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,item] of Object.entries(attributes))value.setAttribute(key,item);if(text!==undefined)value.textContent=text;return value; }
  function show(mode) {
    find('guide-content').hidden=mode==='practice';find('practice-slot').hidden=mode!=='practice';
    find('guide-tab').classList.toggle('active',mode!=='practice');find('practice-tab').classList.toggle('active',mode==='practice');
    find('guide-tab').setAttribute('aria-pressed',String(mode!=='practice'));find('practice-tab').setAttribute('aria-pressed',String(mode==='practice'));
  }
  function network(root) {
    const svg=svgNode('svg',{viewBox:'0 0 270 163',role:'img','aria-label':'입력층 노드 3개, 은닉층 노드 4개, 출력층 노드 2개의 완전 연결 신경망 개념도'});
    const layers=[[[35,45],[35,76],[35,107]],[[133,28],[133,58],[133,88],[133,118]],[[231,61],[231,101]]];
    for(let layer=0;layer<2;layer++)for(const source of layers[layer])for(const target of layers[layer+1])svg.append(svgNode('line',{x1:source[0],y1:source[1],x2:target[0],y2:target[1],class:'network-link','data-layer':layer+1}));
    layers.forEach((items,layer)=>items.forEach(([cx,cy])=>svg.append(svgNode('circle',{cx,cy,r:10,class:'network-node','data-layer':layer}))));
    ['입력층','은닉층','출력층'].forEach((label,index)=>svg.append(svgNode('text',{x:layers[index][0][0],y:151,'text-anchor':'middle'},label)));
    root.append(svg);
    const captions=['입력층: 숫자·픽셀 같은 특징을 받아들입니다.','은닉층: 연결의 가중치와 활성화 함수로 특징을 변환합니다.','출력층: 변환된 특징으로 분류 점수나 예측값을 만듭니다.'];
    function highlight(stage) {
      svg.querySelectorAll('.network-node').forEach(item=>item.classList.toggle('lit',Number(item.dataset.layer)===stage));
      svg.querySelectorAll('.network-link').forEach(item=>item.classList.toggle('lit',stage>0&&Number(item.dataset.layer)===stage));
      [...find('guide-steps').children].forEach((button,index)=>{button.classList.toggle('active',index===stage);button.setAttribute('aria-pressed',String(index===stage));});
      find('guide-caption').textContent=captions[stage];
    }
    ['01 입력','02 변환','03 예측'].forEach((label,index)=>{const button=node('button','',label);button.type='button';button.onclick=()=>highlight(index);find('guide-steps').append(button);});
    highlight(1);
  }
  function render(key) {
    current=key;const concept=concepts[key];find('guide-title').textContent=concept.title;find('guide-description').textContent=concept.description;
    document.querySelectorAll('[data-guide]').forEach(button=>{button.classList.toggle('active',button.dataset.guide===key);button.setAttribute('aria-pressed',String(button.dataset.guide===key));});
    const visual=find('guide-visual');visual.replaceChildren();find('guide-steps').replaceChildren();find('guide-caption').textContent='';
    find('guide-points').replaceChildren(...concept.points.map(point=>node('li','',point)));
    if(concept.type==='network')network(visual);
    if(concept.type==='schema'){
      const table=(title,rows)=>{const card=node('div','schema-table');card.append(node('strong','',title));rows.forEach(([value,key])=>{const row=node('span');if(key)row.append(node('code','',key),document.createTextNode('  '));row.append(document.createTextNode(value));card.append(row);});return card;};
      visual.append(table('학생',[['학생번호','PK'],['이름','']]),node('div','schema-arrow','1  ─────  N'),table('수강',[['수강번호','PK'],['학생번호','FK']]));find('guide-caption').textContent='학생번호를 참조해 학생과 수강 기록을 연결합니다.';
    }
    if(concept.type==='list'){
      const list=node('div','list-visual');[10,20,30].forEach((value,index)=>{const item=node('div','list-element');item.append(node('strong','',value),node('small','',`index ${index}`));list.append(item);});
      visual.append(list,node('div','code-note','items = [10, 20, 30]\nitems[0]  # 10\nitems.append(40)'));find('guide-caption').textContent='순서가 있는 데이터를 인덱스로 읽고, 새 값을 뒤에 추가합니다.';
    }
    if(concept.type==='dataset'){
      const bars=node('div','dataset-blocks');['학습 60%','검증 20%','테스트 20%'].forEach(value=>bars.append(node('span','',value)));visual.append(bars,node('div','code-note','학습 → 설정 비교 → 최종 평가'));find('guide-caption').textContent='세 집합의 역할을 구분하는 개념 예시입니다.';
    }
    if(concept.type==='evaluation'){
      const table=node('table','evaluation-matrix');const header=node('tr');['','예측 +','예측 −'].forEach(value=>header.append(node('th','',value)));table.append(header);
      [['실제 +','TP','FN'],['실제 −','FP','TN']].forEach(values=>{const row=node('tr');values.forEach(value=>row.append(node('td','',value)));table.append(row);});visual.append(table);find('guide-caption').textContent='혼동행렬의 네 가지 경우로 분류 모델의 오류를 구분합니다.';
    }
  }
  return {
    init() {document.querySelectorAll('[data-guide]').forEach(button=>button.onclick=()=>{render(button.dataset.guide);show('guide');document.dispatchEvent(new CustomEvent('loop-guide-topic',{detail:{topicId:concepts[button.dataset.guide].topic}}));});find('guide-tab').onclick=()=>show('guide');find('practice-tab').onclick=()=>show('practice');render('ai');show('guide');},
    select(topicId) {if(concepts[current].topic!==Number(topicId))render(({1:'sql',2:'python',3:'ai'})[topicId]||'ai');},
    sync(active,questions=false) {find('practice-tab').disabled=!active;if(questions)show('practice');else if(!active)show('guide');},
  };
})();
