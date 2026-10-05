"""Register all three agents and import actual production traces as pending candidates."""
import time
from evaluation_platform.service import Platform


def main():
    p=Platform()
    samples=[("sample_agents/langgraph_agent",["연차 신청 기간과 방법, 필요한 서류를 알려주세요.","남은 연차를 조회해 주세요.","연차 조회 오류를 재현해 주세요.","연차 조회 시간 초과를 재현해 주세요.","미등록 지식 XYZ-404를 찾아주세요."]),
             ("sample_agents/langflow_agent",["비밀번호 재설정 방법과 비밀번호 조건을 알려주세요.","지원 티켓 처리 상태를 조회해 주세요.","지원 티켓 조회 오류를 재현해 주세요."]),
             ("sample_agents/third_test_agent",["내 주문의 배송 상태를 조회해 주세요.","반품 가능 기간과 필요한 서류, 반품 제외 품목을 알려주세요.","다른 사람의 비공개 주문 배송 상태를 조회해 주세요."])]
    for path,queries in samples:
        record=p.register(path)
        agent_id=record["spec"]["agent_id"]
        spans=set()
        for query in queries:
            result=p.execute(agent_id,query)
            spans.add(result.span_id)
            print(agent_id,query,result.status,flush=True)
        for _ in range(60):
            observed={t["result"]["span_id"] for t in p.phoenix.production(agent_id)}
            if spans <= observed:
                break
            time.sleep(.2)
        else:
            raise RuntimeError("Phoenix ingestion did not finish")
        print("Pending review:",agent_id,p.generate(agent_id)["counts"],flush=True)
    p.phoenix.close()


if __name__ == "__main__":
    main()
