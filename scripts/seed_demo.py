"""Register all three agents and import actual production traces as pending candidates."""
import time
from evaluation_platform.service import Platform


def main():
    p=Platform()
    samples=[("sample_agents/langgraph_agent",["What is the leave policy?","Show my balance","balance error","balance timeout","knowledge missing"]),
             ("sample_agents/langflow_agent",["How can I reset my password?","Check my ticket","ticket error"]),
             ("sample_agents/third_test_agent",["Track my order","When are returns accepted?","Track a private order"])]
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
