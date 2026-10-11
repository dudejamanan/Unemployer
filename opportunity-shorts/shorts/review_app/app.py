from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
from shorts.pipeline import Pipeline, IST
from shorts.models import ScriptDoc
from shorts.scheduler import schedule


def main():
    st.set_page_config(page_title='Opportunity Shorts Review', layout='wide')
    st.title('Opportunity Shorts')
    pipeline = Pipeline(os.getenv('SHORTS_CONFIG_DIR'))
    try:
        automatic = pipeline.settings['automation']['enabled']
        if automatic:
            st.info('Automatic mode: listings and videos need no manual approval. The worker generates and publishes scheduled videos.')
        status = st.sidebar.selectbox('Queue', ['new', 'approved', 'rejected', 'posted'])
        from collector.config import load_boards, load_sources_cfg
        from collector.pipeline import build_targets
        sources = build_targets(load_boards(os.getenv('SHORTS_CONFIG_DIR')), load_sources_cfg(os.getenv('SHORTS_CONFIG_DIR')))
        with st.sidebar.expander(f'Sources ({len(sources)} enabled)'):
            st.caption('Public feeds use no API key. Listings must be early-career and accept Indian applicants; office location may be abroad.')
            for source, config in sources:
                st.write(config.get('company') or config.get('name') or source.key(config))
        today = datetime.now(IST).date()
        count = pipeline.db.queue_count(status=status, only_open=status != 'posted', today=today)
        page = st.sidebar.number_input('Page', min_value=1, max_value=max(1, (count + 49) // 50), value=1, step=1, key=f'page-{status}')
        cards = pipeline.db.list(status=status, limit=50, offset=(page-1)*50, only_open=status != 'posted', today=today)
        st.caption(f'{count} opportunities in the {status} queue. Page {page} shows {len(cards)} listings.')
        if not cards:
            st.info('No opportunities in this queue. Import a listing or run the collector.')
            return
        rows = {r['id']: r for r in cards}
        opportunity_id = st.selectbox('Opportunity', list(rows), format_func=lambda key: f"{rows[key]['company']} — {rows[key]['title']} ({rows[key]['score']:.0f})")
        from collector.db import row_to_card
        card = row_to_card(rows[opportunity_id])
        st.subheader(f"{card['company']} — {card['role']}")
        st.link_button('Open source listing', card['apply_url'])
        from collector.filters import india_eligibility
        from collector.models import Opportunity
        eligible, evidence = india_eligibility(Opportunity('review', 'review', card['id'], card['role'], card['company'], card['apply_url'],
            location=card['location'], description=card['description'], is_india=card['is_india'], is_remote=card['is_remote']))
        st.caption(f'Applicant eligibility: {evidence}. Verify citizenship, residence, work authorization, and visa requirements before approving.')
        st.write(card['description'])
        for field in ('deadline', 'stipend'):
            if not card[field]:
                st.warning(f'No {field} supplied; verify on the official site.')
        if not card['verified'] and not automatic:
            st.warning('Feed listing requires manual verification.')
        st.json({key: card[key] for key in ('location', 'stipend', 'batch_years', 'experience', 'deadline')})
        left, right = st.columns(2)
        if not automatic and left.button('Approve opportunity'):
            pipeline.card(opportunity_id)
            pipeline.db.set_status(opportunity_id, 'approved')
            st.rerun()
        if right.button('Reject opportunity'):
            pipeline.db.set_status(opportunity_id, 'rejected')
            st.rerun()
        if st.button('Generate video'):
            with st.spinner('Generating narration and video…'):
                pipeline.build(opportunity_id)
            st.rerun()
        post = pipeline.posts.get(opportunity_id)
        if post:
            st.write(f'Video status: {post.status}')
            if post.error_message:
                st.error(post.error_message)
            if post.video_path and Path(post.video_path).exists():
                st.video(post.video_path)
            edited = st.text_area('Script JSON — edits must pass fact validation', json.dumps(json.loads(post.script_json), ensure_ascii=False, indent=2), height=350, key=f'script-{opportunity_id}')
            if st.button('Save edits and regenerate'):
                pipeline.script(opportunity_id, ScriptDoc.from_dict(json.loads(edited)))
                pipeline.build(opportunity_id, force=True)
                st.rerun()
            if post.status == 'generated' and st.button('Approve this video for upload'):
                pipeline.approve_video(opportunity_id)
                st.rerun()
            if post.status == 'ready':
                if st.button('Export for YouTube Studio'):
                    st.success(str(pipeline.upload(opportunity_id, manual_export=True)))
                when = st.text_input('Schedule (IST, ISO date and time)', (datetime.now(IST)+timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0).isoformat())
                if st.button('Schedule approved video'):
                    schedule(pipeline, opportunity_id, when)
                    st.success('Scheduled. The run-daily --upload runner publishes due videos.')
                confirmed = automatic or st.checkbox('Upload this reviewed video to my authorized YouTube channel')
                if st.button('Upload now', disabled=not confirmed):
                    st.success(f"YouTube video: {pipeline.upload(opportunity_id)}")
    except Exception as exc:
        st.error(str(exc))
    finally:
        pipeline.close()


if __name__ == '__main__':
    main()
