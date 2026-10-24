"""Deterministic LinkedIn opportunity cards rendered from stored listing facts."""
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont

WIDTH,HEIGHT=1200,628
PALETTE={'background':'#0b1218','panel':'#101c24','orange':'#ff783d','white':'#f4f6f6','muted':'#aebcc3','mint':'#6ef2b5'}


def font(size,serif=False):
    names=['C:/Windows/Fonts/georgia.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'] if serif else ['C:/Windows/Fonts/segoeui.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for name in names:
        if Path(name).is_file():return ImageFont.truetype(name,size)
    return ImageFont.load_default(size=size)


def clean(value):
    return re.sub(r'\s+',' ',re.sub(r'<[^>]*>',' ',str(value or ''))).strip()


def wrap(draw,text,face,width):
    lines=[];line=''
    for word in text.split():
        if draw.textlength(word,font=face)>width:
            if line:lines.append(line);line=''
            part=''
            for char in word:
                if draw.textlength(part+char,font=face)>width:
                    lines.append(part);part=''
                part+=char
            line=part
        elif draw.textlength((line+' '+word).strip(),font=face)<=width:line=(line+' '+word).strip()
        else:lines.append(line);line=word
    if line:lines.append(line)
    return lines


def facts(row):
    row=dict(row)
    title=clean(row.get('title'))
    if not title:raise ValueError('A source role title is required')
    from .render.render_scenes import cover_compensation
    pay=clean(row.get('stipend_text'))
    amount,period=cover_compensation(pay)
    if period:pay=amount+' / '+('month' if period=='per month' else 'year')
    return {'title':title,'company':clean(row.get('company')) or 'Employer not disclosed',
            'location':clean(row.get('location')) or 'Location not disclosed',
            'type':'Internship' if row.get('opp_type')=='internship' else 'Early-career role',
            'pay':pay or 'Compensation not disclosed',
            'deadline':clean(row.get('deadline'))}


def render_card(row,output):
    data=facts(row)
    image=Image.new('RGB',(WIDTH,HEIGHT),PALETTE['background']);draw=ImageDraw.Draw(image)
    draw.polygon([(710,HEIGHT),(WIDTH,350),(WIDTH,HEIGHT)],fill=PALETTE['panel'])
    draw.text((54,30),'unemployer',font=font(25),fill=PALETTE['mint'])
    company=data['company']
    while draw.textlength(company,font=font(23))>780:company=company[:-2]
    if company!=data['company']:company=company.rstrip()+'…'
    draw.text((54,85),company,font=font(23),fill=PALETTE['white'])
    title=data['title']
    for size in range(100,31,-2):
        face=font(size,True);lines=wrap(draw,title,face,1092)
        if len(lines)*(size+8)<=266:break
    if len(lines)*(size+8)>266:raise ValueError('Role title exceeds card layout; use a separately verified short title')
    top=125+(266-len(lines)*(size+8))//2
    for i,line in enumerate(lines):draw.text((50,top+i*(size+8)),line,font=face,fill=PALETTE['orange'])
    draw.line((54,426,1146,426),fill='#2a3943',width=1)
    fields=[('Location',data['location']),('Opportunity',data['type']),('Listed pay',data['pay'])]
    for x,(label,value),width in zip([54,430,730],fields,[340,260,416]):
        draw.text((x,448),label,font=font(18),fill=PALETTE['muted'])
        values=wrap(draw,value,font(25),width)
        if len(values)>3:raise ValueError('Source facts exceed card layout')
        for i,line in enumerate(values):draw.text((x,478+i*30),line,font=font(25),fill=PALETTE['white'])
    footer='Apply by '+data['deadline']+'  |  ' if data['deadline'] else ''
    draw.text((54,588),footer+'Check eligibility and apply through the source link in the post.',font=font(17),fill=PALETTE['muted'])
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    from PIL.PngImagePlugin import PngInfo
    metadata=PngInfo();metadata.add_text('listing_id',str(dict(row).get('id','preview')))
    image.save(output,format='PNG',optimize=True,pnginfo=metadata)
    return output


def main():
    import argparse
    from .pipeline import Pipeline
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id',required=True);parser.add_argument('--output')
    args=parser.parse_args();p=Pipeline()
    try:
        row=p.db.get(args.id)
        if row is None:raise ValueError('Unknown or ambiguous opportunity ID')
        p.card(row['id'])
        output=args.output or str(Path(p.settings['paths']['output_dir'])/'linkedin'/row['id']/'card.png')
        print(render_card(row,output))
        from .linkedin import commentary
        caption=Path(output).with_suffix('.txt')
        caption.write_text(commentary(row),encoding='utf-8')
        print(caption)
    finally:p.close()

if __name__=='__main__':main()
