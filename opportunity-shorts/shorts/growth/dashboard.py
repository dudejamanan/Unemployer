"""Local-only inspection and revision controls; no approval gate."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path


def show(pipeline,st):
    conn=pipeline.posts.conn
    with st.expander('Audience growth and career research'):
        st.caption('Autonomous evidence validation. No human approval is required; failed research is deferred.')
        rows=conn.execute('SELECT * FROM career_topics ORDER BY discovered_at').fetchall()
        if not rows:
            st.info('No topics yet. Run: python -m shorts growth discover')
        else:
            topics={r['id']:r for r in rows}
            id=st.selectbox('Career topic',list(topics),format_func=lambda id:topics[id]['title'],key='growth-topic')
            topic=topics[id]
            st.write('State: '+topic['status'])
            if topic['error']:st.warning(topic['error'])
            for source in conn.execute('SELECT DISTINCT s.* FROM career_sources s JOIN career_claims c ON c.source_id=s.id WHERE c.topic_id=?',(id,)):
                st.link_button(source['title'],source['url'])
            st.dataframe([dict(r) for r in conn.execute('SELECT id,source_id,quote,kind,verified_at FROM career_claims WHERE topic_id=?',(id,))],use_container_width=True)
            if topic['brief']:st.json(json.loads(topic['brief']))
            if topic['script']:st.code(json.dumps(json.loads(topic['script']),ensure_ascii=False,indent=2),language='json')
            if topic['content_id']:
                content=conn.execute('SELECT * FROM content_items WHERE id=?',(topic['content_id'],)).fetchone()
                if content and content['video_path'] and Path(content['video_path']).exists():st.video(content['video_path'])
            reason=st.text_input('Revision or rejection reason',key='growth-reason')
            if topic['status']!='published' and st.button('Request evidence-based revision',disabled=not reason):
                from .store import update_topic,ensure_mutable
                try:ensure_mutable(conn,topic['content_id'])
                except ValueError as exc:st.error(str(exc));return
                update_topic(conn,id,'researched' if topic['brief'] else 'discovered',error=reason,retry_after=None)
                if topic['content_id']:conn.execute("UPDATE content_items SET status='deferred' WHERE id=?",(topic['content_id'],));conn.commit()
                st.rerun()
            if topic['status']!='published' and st.button('Reject topic',disabled=not reason):
                from .store import update_topic,ensure_mutable
                try:ensure_mutable(conn,topic['content_id'])
                except ValueError as exc:st.error(str(exc));return
                update_topic(conn,id,'rejected',error=reason)
                if topic['content_id']:conn.execute("UPDATE content_items SET status='rejected' WHERE id=?",(topic['content_id'],));conn.commit()
                st.rerun()
        st.dataframe([dict(r) for r in conn.execute('SELECT * FROM content_deliveries')],use_container_width=True)
        from .reporting import report
        performance=report(conn)
        for note in performance['limits']:st.caption(note)
        st.json(performance)
        st.dataframe([dict(r) for r in conn.execute('SELECT * FROM growth_experiments')],use_container_width=True)
        st.dataframe([dict(r) for r in conn.execute('SELECT organization,category,message_status,follow_up_date,partnership_status FROM outreach_contacts')],use_container_width=True)

        st.dataframe([dict(r) for r in conn.execute('SELECT * FROM growth_jobs')],use_container_width=True)
        st.dataframe([dict(r) for r in conn.execute('SELECT * FROM guide_sync')],use_container_width=True)
        from .revenue import summary
        st.json(summary(conn))
