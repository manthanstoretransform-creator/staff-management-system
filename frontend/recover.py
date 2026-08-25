import json
import ast

def main():
    target = r"c:\Users\PC - 18\Desktop\Staff Management\staff-management-system\frontend\src\features\dashboard\v2\DashboardV2.tsx"
    log_file = r"C:\Users\PC - 18\.gemini\antigravity\brain\cd38584f-3698-448c-809d-7746937b97c8\.system_generated\logs\transcript_full.jsonl"
    
    with open(log_file, encoding='utf-8') as f:
        for line in f:
            try:
                d = json.loads(line)
                if 'tool_calls' in d:
                    for call in d['tool_calls']:
                        if call['name'] == 'write_to_file':
                            args = call.get('args', {})
                            if 'DashboardV2.tsx' in args.get('TargetFile', ''):
                                code = args['CodeContent']
                                if code.startswith('"'):
                                    code = ast.literal_eval(code)
                                with open(target, 'w', encoding='utf-8') as out:
                                    out.write(code)
            except Exception as e:
                pass

if __name__ == '__main__':
    main()
