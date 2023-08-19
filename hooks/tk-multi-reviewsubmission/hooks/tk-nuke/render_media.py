import sgtk
import os
import nuke

HookBaseClass = sgtk.get_hook_baseclass()

class RenderMedia(HookBaseClass):
    """
    RenderMedia hook implementation for the tk-nuke engine.
    """

    def __init__(self, *args, **kwargs):
        super(RenderMedia, self).__init__(*args, **kwargs)
        self.__app = self.parent

    def __create_gamma_node(self):
        """
        Create the Nuke gamma correction node.

        :returns: Pre-configured Gamma node
        :rtype: Nuke node
        """
        gamma_node = nuke.nodes.Gamma()
        gamma_node['value'].setValue(0.5)
        return gamma_node


    def render(
        self,
        input_path,
        output_path,
        width,
        height,
        first_frame,
        last_frame,
        version,
        name,
        color_space,
    ):
        """
        Use Nuke to render a movie.

        :param str input_path:      Path to the input frames for the movie
        :param str output_path:     Path to the output movie that will be rendered
        :param int width:           Width of the output movie
        :param int height:          Height of the output movie
        :param int first_frame:     The first frame of the sequence of frames.
        :param int last_frame:      The last frame of the sequence of frames.
        :param str version:         Version number to use for the output movie
        :param str name:            Name to use in the slate for the output movie
        :param str color_space:     Colorspace of the input frames

        :returns:               Location of the rendered media
        :rtype:                 str
        """
        output_node = None
        ctx = self.__app.context

        # create group where everything happens
        group = nuke.nodes.Group()

        # now operate inside this group
        group.begin()
        try:
            # create read node
            read = nuke.nodes.Read(name="source", file=input_path.replace(os.sep, "/"))
            read["on_error"].setValue("black")
            read["first"].setValue(first_frame)
            read["last"].setValue(last_frame)
            if color_space:
                read["colorspace"].setValue(color_space)

            # create a scale node
            scale = self.__create_scale_node(width, height)
            scale.setInput(0, read)

            # create a gamma correction node
            gamma_node = self.__create_gamma_node()
            gamma_node.setInput(0, scale)

            # Create the output node
            output_node = self.__create_output_node(output_path)
            output_node.setInput(0, scale)
        finally:
            group.end()

        if output_node:
            # Make sure the output folder exists
            output_folder = os.path.dirname(output_path)
            self.__app.ensure_folder_exists(output_folder)

            # Render the outputs, first view only
            nuke.executeMultiple(
                [output_node], ([first_frame - 1, last_frame, 1],), [nuke.views()[0]]
            )

        # Cleanup after ourselves
        nuke.delete(group)

        return output_path

    def __create_scale_node(self, width, height):
        """
        Create the Nuke scale node to resize the content.

        :param int width:           Width of the output movie
        :param int height:          Height of the output movie

        :returns:               Pre-configured Reformat node
        :rtype:                 Nuke node
        """
        scale = nuke.nodes.Reformat()
        scale["type"].setValue("to box")
        scale["box_width"].setValue(width)
        scale["box_height"].setValue(height)
        scale["resize"].setValue("fit")
        scale["box_fixed"].setValue(True)
        scale["center"].setValue(True)
        scale["black_outside"].setValue(True)
        return scale

    def __create_output_node(self, path):
        """
        Create the Nuke output node for the movie.

        :param str path:           Path of the output movie

        :returns:               Pre-configured Write node
        :rtype:                 Nuke node
        """
        # get the Write node settings we'll use for generating the Quicktime
        wn_settings = self.__get_quicktime_settings()

        node = nuke.nodes.Write(file_type=wn_settings.get("file_type"))

        # apply any additional knob settings provided by the hook. Now that the knob has been
        # created, we can be sure specific file_type settings will be valid.
        for knob_name, knob_value in six.iteritems(wn_settings):
            if knob_name != "file_type":
                node.knob(knob_name).setValue(knob_value)

        # Don't fail if we're in proxy mode. The default Nuke publish will fail if
        # you try and publish while in proxy mode. But in earlier versions of
        # tk-multi-publish (< v0.6.9) if there is no proxy template set, it falls
        # back on the full-res version and will succeed. This handles that case
        # and any custom cases where you may want to send your proxy render to
        # screening room.
        root_node = nuke.root()
        is_proxy = root_node["proxy"].value()
        if is_proxy:
            self.__app.log_info("Proxy mode is ON. Rendering proxy.")
            node["proxy"].setValue(path.replace(os.sep, "/"))
        else:
            node["file"].setValue(path.replace(os.sep, "/"))

        return node

    def __get_quicktime_settings(self, **kwargs):
        """
        Allows modifying default codec settings for Quicktime generation.
        Returns a dictionary of settings to be used for the Write Node that generates
        the Quicktime in Nuke.

        :returns:               Codec settings
        :rtype:                 dict
        """
        settings = {}
        if sgtk.util.is_windows() or sgtk.util.is_macos():
            settings["file_type"] = "mov"
            if nuke.NUKE_VERSION_MAJOR >= 9:
                settings["meta_codec"] = "jpeg"
                settings["mov64_quality_max"] = "3"
            else:
                settings["codec"] = "jpeg"

        elif sgtk.util.is_linux():
            if nuke.NUKE_VERSION_MAJOR >= 9:
                settings["file_type"] = "mov64"
                settings["mov64_codec"] = "jpeg"
                settings["mov64_quality_max"] = "3"
            else:
                settings["file_type"] = "ffmpeg"
                settings["format"] = "MOV format (mov)"

        return settings
