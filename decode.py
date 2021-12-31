import os
import sqlite3
import json
import struct
import skia
import argparse
try:
  from IPython.display import display, Image
  iPython_available = True
except:
    pass

dirName = "/home/amd/work/reverse/Test4"

def read_shape_db(dir, id, pageId):
    shapes = []
    hwr = []
    db_file = os.path.join(dir, f"{id}.db")
    con = sqlite3.connect(db_file)
    con.isolation_level = None
    con.row_factory = sqlite3.Row
    cursor = con.execute(f"SELECT * FROM NewShapeModel where pageUniqueId = '{pageId}'")
    for row in cursor:
        #print(f"{row['pageUniqueId']} {pageId}")
        if row['matrixValues'] != None and row['boundingRect'] != None:
            shapes.append({"shapeId": row['shapeUniqueId'], 
                       "documentId": row['documentUniqueId'], 
                       "pageId": row['pageUniqueId'],
                       "boundingRect": json.loads(row['boundingRect']),
                       "matrix": json.loads(row['matrixValues']),
                       "status": row['status']
                          })
    cursor = con.execute(f"SELECT * FROM HWRDataModel where pageUniqueId = '{pageId}'")
    for row in cursor:
        hwr.append({
            "result": row['hwrResult'],
            "candidates": row['candidates'],
            "boundingRect": json.loads(row['boundingRect']),
        })
    return shapes, hwr
        
def read_db(dir):
    db_file = os.path.join(dir, "ShapeDatabase.db")
    con = sqlite3.connect(db_file)
    con.isolation_level = None
    con.row_factory = sqlite3.Row
    cursor = con.execute("SELECT * FROM NoteModel")
    notebooks = {"basedir": dir, "notebooks": [] }
    for row in cursor:
        pageNameList = json.loads(row['pageNameList'])
        pageInfo = json.loads(row['notePageInfo'])
        notebook = { "name": row['title'], "id": row['uniqueId'], "info": pageInfo, "pages": [] }
        pageNr = 0
        for pageId in pageNameList['pageNameList']:
            pageNr = pageNr + 1
            points_files = []
            shapes = []
            hwr = []
            info = {}
            if pageId in pageInfo['pageInfoMap']:
                info = pageInfo['pageInfoMap'][pageId]
            point_dir = os.path.join(dir, "point", notebook['id'], pageId)
            if os.path.isdir(point_dir):
                points_files = os.listdir(point_dir)
                shapes, hwr = read_shape_db(dir, notebook['id'], pageId)
                
            notebook['pages'].append({"pageNr": pageNr, "id": pageId, "info": info, "hwr": hwr, "shapes": shapes, "points": points_files})
        notebooks['notebooks'].append(notebook)
    return notebooks


def point(f, dbg):
    size = struct.unpack(">f", f.read(4))[0]
    x = struct.unpack(">f", f.read(4))[0]
    y = struct.unpack(">f", f.read(4))[0]
    p = struct.unpack(">i", f.read(4))[0]
    #t = struct.unpack(">q", f.read(8))[0]
    if (dbg):
        print(f"x: {x:.2f}, y: {y:.2f}, p: {p:.2f}")
    return (x, y)

def get_file_info(fileName, dbg):
    size = os.path.getsize(fileName)
    shapes = []
    with open(fileName, mode='rb') as f:
        f.seek(size-4)
        end_block_start = struct.unpack(">i", f.read(4))[0]
        f.seek(end_block_start)
        shape_count = (size-4-end_block_start)/44
        if shape_count != int(shape_count):
            print("ERROR, shape count calculation wrong")
            exit(1)
        if dbg:
            print(f"End block starts at {end_block_start}, number of shapes: {shape_count}")
            
        for i in range(int(shape_count)):

            uid = struct.unpack("36s", f.read(36))[0]
            start = struct.unpack(">i", f.read(4))[0]
            length = struct.unpack(">i", f.read(4))[0]
            count = int(length/16)
            shapes.append({"id": uid, "start": start, "length": length, "count": count})
            if dbg:
                print(f"shape {uid}: from {start} ({count} shapes)")
    return shapes
    
def read_points_file(fileName, shapes, dbg):
    header_size = 80
    points = []
    with open(fileName, mode='rb') as f: # b is important -> binary
        version = struct.unpack(">I", f.read(4))[0]
        uid = struct.unpack("36s", f.read(36))[0]
        uid = struct.unpack("36s", f.read(36))[0]
        unknown = struct.unpack(">f", f.read(4))[0]
        if dbg:
            print(f"version: {version}")
            print(f"uid: {uid}")
            print(f"uid: {uid}")
        for shape in shapes:
            current_points = ([], [], shape['id'].decode('UTF-8'))
            f.seek(shape['start'])
            if dbg:
                print(f"drawing shape {shape['id']} with {shape['count']} strokes")
            for i in range(shape['count']):
                if dbg:
                    print(f"{i:02x}", end =", ")
                (x,y) = point(f, dbg)
                current_points[0].append(x)
                current_points[1].append(y)
            points.append(current_points)
    return points

def get_page_data(notebooks, name, pageNr):
    point_files = []
    info = {}
    shapes = []
    hwr = []
    for notebook in notebooks['notebooks']:
        if notebook['name'] == name:
            pages = notebook['pages']
            for page in pages:
                if page['pageNr'] == pageNr and len(page['points']) > 0:
                    info = page['info']
                    shapes = page['shapes']
                    hwr = page['hwr']
                    #for shape in page['shapes']:
                    #    print(f"rect: {shape}")
                    #    pass
                    for point in page['points']:
                        file_path = os.path.join(notebooks['basedir'], "point", notebook['id'], page['id'], point)
                        point_files.append(file_path)
    return point_files, info, shapes, hwr

def show_page(notebooks, name, page, words, output, show, dbg):
    found_count = 0
    files, info, shapes, hwr =  get_page_data(notebooks, name, page)
    if dbg:
        print(f"canvas size: {info['width']}x{info['height']}")
    surface = skia.Surface(info['width'], info['height'])
    canvas = surface.getCanvas()
    
    paint = skia.Paint()
    paint.setAntiAlias(True)
    
    found_paint = skia.Paint(
        AntiAlias=True,
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=1,
        Color=skia.ColorRED,
    )

    shapes = {str(shapes[i]['shapeId']): shapes[i] for i in range(0, len(shapes))}
    for file in files:
        points = read_points_file(file, get_file_info(file, dbg), dbg)

        for (x_values, y_values, id) in points:
            path = skia.Path()
            paint.setStyle(skia.Paint.kStroke_Style)
            shape = shapes[id] if id in shapes else None
            if shape != None: #invalid/deleted shapes in db are not printed (they might be in the points file though, so beware!)
                for i in range(len(x_values)):
                    if i == 0:
                        path.moveTo(x_values[i], y_values[i])
                    else:
                        path.lineTo(x_values[i], y_values[i])
                if shape['matrix'] != None and shape['matrix']['values'] != None:
                    path.transform(skia.Matrix(shape['matrix']['values']))

            canvas.drawPath(path, paint)
            paint.setColor(skia.ColorBLUE)
            paint.setStrokeWidth(2)
            canvas.drawPath(path, paint)
            
        for word in words:
            found_items = filter(lambda x: x['result'].lower() == word, hwr)
            for found in found_items:
                found_count = found_count + 1
                r = found['boundingRect']
                rect = skia.Rect(r['left'],r['top'],r['right'],r['bottom'])
                canvas.drawRect(rect, found_paint)
                        
    image = surface.makeImageSnapshot()
    if output != None:
        image.save(output, skia.kPNG)
    if iPython_available and show:
        display(Image(data=image.encodeToData()))
    return found_count

parser = argparse.ArgumentParser(description='Parse a Boox Notes backup and search/show/save a page.')
parser.add_argument('--directory', dest='dir', required=True,
                    help='Directory of the Boox Notes backup')
parser.add_argument('--output', dest='output',
                    help='Save page as png file')
parser.add_argument('--notebook', dest='notebook',
                    help='Notebook name')
parser.add_argument('--page', dest='page', type=int,
                    help='Notebook page')
parser.add_argument('--show', dest='show', action='store_true',
                    help='show result (needs Jupyter/iPython)')
parser.add_argument('--find', dest="words", nargs='*', help='find words on page', default=[])
args = parser.parse_args()

if args.notebook == None:
    notebooks = read_db(args.dir)
    notebook_names = [notebook['name'] for notebook in notebooks['notebooks']]
    notebook_pages = { notebook['name']: [page['pageNr'] for page in notebook['pages']] for notebook in notebooks['notebooks'] }
    print("Notebooks:")
    for notebook in notebook_names:
        print(f"  {notebook}:\t\t\t\t{len(notebook_pages[notebook])} pages")
else:
    dbg = False
    if args.page != None:
        found_count = show_page(read_db(args.dir), args.notebook, args.page, args.words, args.output, args.show, dbg)
        if len(args.words) > 0:
            print(f"Found {found_count} words")
    else:
        print("Missing page, use --page <page>")
