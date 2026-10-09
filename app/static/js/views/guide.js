import { DEPTH, esc } from "../util.js";

export async function render(root) {
  root.innerHTML = `<div class="page">
    <div class="page-head"><div><h1>사용법</h1><p>이 앱이 전제하는 공부 방식과, 화면을 어디서 무엇에 쓰는지.</p></div></div>

    <div class="card"><h2>원칙: 내가 쓰고, Claude가 검사한다</h2>
      <div class="md" style="margin-top:8px">
        <p>논문 요약을 받아 읽는 것은 공부한 느낌만 줍니다. 이 앱은 반대 방향으로 씁니다.</p>
        <ul>
          <li><strong>읽기</strong>와 <strong>노트 쓰기</strong>는 직접 합니다.</li>
          <li>Claude는 내 노트를 논문과 대조해 <strong>틀린 곳을 지적</strong>하고, <strong>구술시험</strong>을 보고, <strong>구현 과제</strong>를 냅니다.</li>
          <li>"완독" 버튼 대신 <strong>이해 깊이</strong>를 단계로 남깁니다. 기준을 스스로 통과했을 때만 올립니다.</li>
        </ul></div></div>

    <div class="card"><h2>이해 깊이 네 단계</h2>
      <table class="activity" style="margin-top:8px"><tbody>${DEPTH.slice(1).map((d, i) => `<tr><td><strong>${i + 1} ${d.label}</strong></td><td></td><td>${esc(d.test)}</td></tr>`).join("")}</tbody></table>
      <p class="small muted" style="margin-top:10px">대부분의 논문은 2(정독)면 충분합니다. 로드맵의 핵심 논문과 업무에 직접 쓰는 논문만 3·4까지 갑니다. 모든 논문을 구현하려 들면 한 달 안에 멈춥니다.</p></div>

    <div class="card"><h2>논문 한 편을 읽는 순서</h2>
      <div class="md" style="margin-top:8px"><ol>
        <li><a href="#/roadmap">로드맵</a>에서 논문을 <code>추가</code>하고, 제목을 눌러 논문 화면으로 갑니다.</li>
        <li><code>읽기 시작</code>으로 타이머를 켜고 <code>arXiv ↗</code> 또는 <code>PDF ↗</code>로 원문을 엽니다.</li>
        <li><strong>1회독(10분)</strong>: 초록·그림·결론만. <code>3회독 템플릿으로 시작</code>을 눌러 첫 절을 채우고, 이해 깊이를 1로.</li>
        <li><strong>2회독(1시간)</strong>: 그림과 표를 하나씩 직접 해석해 표를 채웁니다. 끝나면 <code>Claude와 공부하기 → 내 노트 검토받기</code>. 지적받은 곳을 직접 고치고 깊이를 2로.</li>
        <li><strong>3회독</strong>: 핵심 식 하나를 손으로 유도하고 의사코드를 씁니다. <code>구술시험 보기</code>로 확인하고 깊이를 3으로.</li>
        <li><strong>구현</strong>: <code>구현 과제 받기</code>로 과제와 채점 테스트를 받아 직접 짭니다. 통과하면 깊이를 4로, 구현 위치를 적습니다.</li>
        <li>노트 끝의 <code>Q:</code> / <code>A:</code>는 복습 카드가 됩니다. 사실보다 "왜"와 유도를 묻는 카드를 만듭니다.</li>
      </ol></div></div>

    <div class="card"><h2>기초가 흔들린다면: 구현 과제부터</h2>
      <p style="margin-top:8px">논문을 읽다가 역전파나 attention에서 막힌다면 읽기를 멈추고 <a href="#/practice">구현 과제</a>를 먼저 합니다.
        IoU·NMS, conv 역전파, BatchNorm, Adam, attention 등 아홉 개가 있고, 각각 손으로 풀 유도 문제와 자동 채점 스크립트가 딸려 있습니다.
        YOLO를 읽었다면 <strong>02 IoU와 NMS</strong>, <strong>07 Focal Loss</strong>가 익숙한 데서 출발하는 과제입니다.</p></div>

    <div class="card"><h2>매일의 흐름 (퇴근 후 한 시간)</h2>
      <div class="md" style="margin-top:8px"><ol>
        <li><a href="#/">홈</a>을 열면 맨 위에 <strong>지금 할 일</strong> 하나가 나옵니다. 보통 밀린 복습 카드입니다 (5~10분).</li>
        <li>복습에서 카드가 틀렸거나 어색하면 그 자리에서 고칩니다. 잘못 누른 평가는 <kbd>u</kbd>로 되돌립니다.</li>
        <li>남은 시간은 읽던 논문 한 편 또는 구현 과제 하나에 씁니다. 둘을 섞지 않습니다.</li>
        <li>완독하고 일주일 뒤 <strong>복습 → 논문 회상</strong>이 그 논문을 기억만으로 다시 쓰게 합니다.</li>
      </ol></div></div>

    <div class="card"><h2>화면별 용도</h2>
      <table class="activity" style="margin-top:8px"><tbody>
        <tr><td><a href="#/">홈</a></td><td></td><td>지금 할 일, 이번 주 목표, 학습 기록, 월별 추이</td></tr>
        <tr><td><a href="#/search">검색</a></td><td></td><td>arXiv 검색. ID나 링크를 붙여넣으면 바로 조회. 자주 보는 검색은 저장해 새 논문 알림을 받음</td></tr>
        <tr><td><a href="#/library">라이브러리</a></td><td></td><td>저장한 논문. 노트 본문까지 검색. '연결 지도'에서 논문 사이의 관계를 봄</td></tr>
        <tr><td><a href="#/review">복습</a></td><td></td><td>오늘 복습(카드), 논문 회상(완독한 논문을 기억으로 요약), 약점(자주 틀리는 주제)</td></tr>
        <tr><td><a href="#/roadmap">로드맵</a></td><td></td><td>읽기 순서(분야별 트랙)와 구현 과제</td></tr>
        <tr><td><a href="#/surveys">서베이</a></td><td></td><td>새 분야에 들어갈 때 흐름을 정리한 문서</td></tr>
        <tr><td><a href="#/settings">설정</a></td><td></td><td>테마, 주간 목표, 백업, 단축키(<kbd>?</kbd>)</td></tr>
      </tbody></table></div>

    <div class="card"><h2>켜는 법</h2>
      <p style="margin-top:8px">터미널에서 <code>cd ~/works/paper_study && ./run.sh</code>. 브라우저가 열립니다. 끄려면 터미널에서 <kbd>Ctrl</kbd>+<kbd>C</kbd>.
        Claude Code는 같은 폴더에서 열어야 노트 파일을 찾습니다.</p></div>
  </div>`;
}
