import math

import click
import numpy as np
from shapely.geometry import MultiLineString, LineString
from svgpathtools import Line, Document

from .utils import Length, convert
from .vpype import cli, generator


@cli.command(group="Input")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-q",
    "--quantization",
    type=Length(),
    default="1mm",
    help="Maximum length of segments approximating curved elements.",
)
@generator
def read(file, quantization: float) -> MultiLineString:
    """
    Extract geometries from a SVG file.

    This command only extracts path elements as well as primitives (rectangles, ellipses,
    lines, polylines, polygons). In particular, text and bitmap images are discarded, as well
    as all formatting.

    All curved primitives (e.g. bezier path, ellipses, etc.) are linearized and approximated
    by polylines. The quantization length controls the maximum length of individual segments
    (1mm by default).
    """

    doc = Document(file)
    results = doc.flatten_all_paths()
    root = doc.tree.getroot()

    # we must interpret correctly the viewBox, width and height attribs in order to scale
    # the file content to proper pixels

    if "viewBox" in root.attrib:
        # A view box is defined so we must correctly scale from user coordinates
        # https://css-tricks.com/scale-svg/
        # TODO: we should honor the `preserveAspectRatio` attribute

        w = convert(root.attrib["width"])
        h = convert(root.attrib["height"])

        viewbox = [float(s) for s in root.attrib["viewBox"].split()]

        scale_x = w / (viewbox[2] - viewbox[0])
        scale_y = h / (viewbox[3] - viewbox[1])
        offset_x = -viewbox[0]
        offset_y = -viewbox[1]
    else:
        scale_x = 1
        scale_y = 1
        offset_x = 0
        offset_y = 0

    ls_array = []
    for result in results:
        for elem in result.path:
            if isinstance(elem, Line):
                coords = np.array([elem.start, elem.end])
            else:
                # This is a curved element that we approximate with small segments
                step = int(math.ceil(elem.length() / quantization))
                coords = np.empty(step + 1, dtype=complex)
                coords[0] = elem.start
                for i in range(step-1):
                    coords[i + 1] = elem.point((i + 1) / step)
                coords[-1] = elem.end

            # convert complex to coordinates
            coords = coords.view(dtype=float).reshape(len(coords), 2)
            final_coords = np.empty_like(coords)
            final_coords[:, 0] = scale_x * (coords[:, 0] + offset_x)
            final_coords[:, 1] = scale_y * (coords[:, 1] + offset_y)

            ls_array.append(LineString(final_coords))

    return MultiLineString(ls_array)