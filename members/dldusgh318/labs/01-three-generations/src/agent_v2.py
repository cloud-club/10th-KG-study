"""기존 생성 설정에 그래프 리트리버만 추가한 에이전트 CLI."""
import argparse
import json
import os

import agent
from common import LAB, load_chunks_by_id
from hybrid_search import hybrid_search
import graph_retriever


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question')
    parser.add_argument('--context-only',action='store_true')
    args=parser.parse_args()
    env=LAB/'.env'
    if env.exists():
        for line in env.read_text().splitlines():
            name,sep,value=line.strip().partition('=')
            if sep and name in ('OPENAI_API_KEY','OPENAI_MODEL'):
                os.environ.setdefault(name,value.strip().strip('\"\''))
    retrieved=hybrid_search(args.question,agent.TOP_K)
    state=graph_retriever.load_graph()
    if args.context_only:
        context,_,trace=graph_retriever.assemble_v2(retrieved,state,load_chunks_by_id())
        print(context)
        print(json.dumps(trace,ensure_ascii=False,indent=2))
    else:
        result=graph_retriever.answer(args.question,retrieved,state)
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
