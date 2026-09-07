# make_test_gds.py
import klayout.db as db  # pip install klayout

layout = db.Layout()
top = layout.create_cell("TOP")

# Confirmed from sky130A.lyp: met1.drawing = GDS layer 68, datatype 20
met1_layer = layout.layer(68, 20)

dbu = layout.dbu
def um(v):
    return int(round(v / dbu))

# Two rectangles with only a 5nm gap between them — deliberately far
# below any real minimum-spacing rule, so this should unambiguously
# violate DRC. Box coordinates are (left, bottom, right, top) in microns.
box1 = db.Box(um(0.0), um(0.0), um(0.5), um(0.5))
box2 = db.Box(um(0.505), um(0.0), um(1.0), um(0.5))

top.shapes(met1_layer).insert(box1)
top.shapes(met1_layer).insert(box2)

layout.write("test_violation.gds")
print("wrote test_violation.gds")