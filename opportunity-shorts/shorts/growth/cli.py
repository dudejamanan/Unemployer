"""Growth commands integrated into python -m shorts."""
import json
from pathlib import Path
from .store import discover,now,identifier,update_topic
from .research import config,seed,research_topic,safe_source
from .model import ask
from .content import draft,build,validate_ready
from .workflow import maintenance,create_roundup
from .reporting import report,import_csv,experiment


def register(sub):
    group=sub.add_parser('growth',help='Autonomous career content, measurement and outreach records')
    commands=group.add_subparsers(dest='growth_command',required=True)
    for name in ('status','discover','run','report','roundup'):
        cmd=commands.add_parser(name)
        if name=='discover':
            cmd.add_argument('--question');cmd.add_argument('--title');cmd.add_argument('--category',default='applications');cmd.add_argument('--source',action='append',default=[])
        if name=='report':cmd.add_argument('--output')
        if name=='roundup':cmd.add_argument('--build',action='store_true')
        cmd.set_defaults(fn=execute)
    for name in ('research','brief','draft','validate','build','revise','reject','publish'):
        cmd=commands.add_parser(name);cmd.add_argument('id')
        if name in ('reject','revise'):cmd.add_argument('--reason',required=True)
        if name=='publish':
            cmd.add_argument('--platform',choices=['youtube','linkedin'],required=True);cmd.add_argument('--dry-run',action='store_true')
        cmd.set_defaults(fn=execute)
    cmd=commands.add_parser('import-metrics');cmd.add_argument('path');cmd.add_argument('--captured-at',required=True);cmd.add_argument('--period-start');cmd.add_argument('--period-end');cmd.set_defaults(fn=execute)
    cmd=commands.add_parser('experiment');cmd.add_argument('--hypothesis',required=True);cmd.add_argument('--variable',required=True);cmd.add_argument('--variants',nargs=2,required=True);cmd.add_argument('--starts-at',required=True);cmd.add_argument('--ends-at',required=True);cmd.set_defaults(fn=execute)
    cmd=commands.add_parser('contact');cmd.add_argument('--organization',required=True);cmd.add_argument('--category',choices=['student_community','employer','college','creator'],required=True);cmd.add_argument('--public-source',required=True);cmd.add_argument('--contact');cmd.set_defaults(fn=execute)


def execute(args):
    from ..pipeline import Pipeline
    p=Pipeline(args.config);conn=p.posts.conn;cfg=config(args.config);command=args.growth_command
    try:
        if command=='status':
            value={'mode':'autonomous; no human approval gate','topics':[dict(r) for r in conn.execute('SELECT id,title,status,error,retry_after FROM career_topics')],
                   'content':[dict(r) for r in conn.execute('SELECT id,format,status,title,error FROM content_items')],
                   'deliveries':[dict(r) for r in conn.execute('SELECT * FROM content_deliveries')],
                   'unavailable_adapters':cfg.get('unavailable_adapters',{})}
        elif command=='discover':
            if args.question:
                for url in args.source:safe_source(url,cfg)
                value={'topic_id':discover(conn,args.title or args.question,args.question,args.category,'manual_student_question',args.source)}
            else:value={'topic_ids':seed(conn,cfg)}
        elif command=='run':value=maintenance(p,args.config)
        elif command=='report':
            value=report(conn)
            if args.output:
                from ..production import atomic_json
                atomic_json(Path(args.output),value)
        elif command=='import-metrics':value={'imported':import_csv(conn,args.path,args.captured_at,args.period_start,args.period_end)}
        elif command=='experiment':value={'experiment_id':experiment(conn,args.hypothesis,args.variable,args.variants,args.starts_at,args.ends_at)}
        elif command=='contact':
            from urllib.parse import urlsplit
            u=urlsplit(args.public_source)
            if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('A public HTTPS professional source is required')
            id=identifier(args.organization+'|'+args.category)
            conn.execute('INSERT OR IGNORE INTO outreach_contacts(id,organization,category,professional_contact,public_source_url) VALUES (?,?,?,?,?)',(id,args.organization,args.category,args.contact,args.public_source));conn.commit()
            value={'contact_id':id,'message_status':'not_sent'}
        elif command=='roundup':
            id=create_roundup(p);value={'content_id':id,'state':'drafted' if id else 'insufficient_fresh_diverse_paid_sources'}
            if id and args.build:value['video']=build(conn,id,p.settings,cfg)
        else:
            topic=conn.execute('SELECT * FROM career_topics WHERE id=?',(args.id,)).fetchone()
            id=topic['content_id'] if topic else args.id
            if command=='research':research_topic(conn,args.id,p.settings,cfg,ask);value={'state':'researched','topic_id':args.id}
            elif command=='brief':value=json.loads(topic['brief']) if topic and topic['brief'] else {'state':'research_required'}
            elif command=='draft':value={'content_id':draft(conn,args.id,p.settings,cfg,ask)}
            elif command=='validate':
                item=conn.execute('SELECT * FROM content_items WHERE id=?',(id,)).fetchone()
                if not item:raise ValueError('Unknown content item')
                value={'valid':validate_ready(conn,item,cfg),'approval_mode':'automated'}
            elif command=='build':value={'video':build(conn,id,p.settings,cfg)}
            elif command in ('revise','reject'):
                if not topic:raise ValueError('Unknown topic')
                if topic['status']=='published':raise ValueError('Published topics are immutable; discover a new follow-up question')
                from .store import ensure_mutable
                ensure_mutable(conn,id)
                update_topic(conn,args.id,'researched' if command=='revise' else 'rejected',error=args.reason)
                if id:conn.execute("UPDATE content_items SET status='deferred',error=? WHERE id=?",(args.reason,id));conn.commit()
                value={'state':command,'topic_id':args.id}
            elif command=='publish':
                item=conn.execute('SELECT * FROM content_items WHERE id=?',(id,)).fetchone()
                if not item:raise ValueError('Unknown content item')
                validate_ready(conn,item,cfg)
                if args.dry_run:value={'dry_run':True,'format':item['format'],'script':json.loads(item['script']),'video_path':item['video_path']}
                else:
                    from .publishing import try_publish
                    value=try_publish(p,args.platform,content_id=id)
        print(json.dumps(value,ensure_ascii=True,indent=2));return 0
    except Exception as exc:
        if command in ('research','draft','build') and 'topic' in locals() and topic:
            from datetime import datetime,timedelta,timezone
            from .store import ensure_mutable
            try:
                ensure_mutable(conn,topic['content_id'])
                if topic['status']!='published':
                    message=str(exc)[:350] if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__
                    update_topic(conn,topic['id'],'deferred',error=message,retry_after=(datetime.now(timezone.utc)+timedelta(hours=6)).isoformat())
            except ValueError:pass
        raise
    finally:p.close()
